from pathlib import Path
import mimetypes
from django.conf import settings
from django.core.exceptions import ValidationError
from django.contrib import messages
from django.contrib.auth import login, logout, views as auth_views
from django.db import transaction, IntegrityError
from django.http import FileResponse, Http404
from django.shortcuts import render, redirect, get_object_or_404
from django.urls import reverse_lazy
from django.utils.http import url_has_allowed_host_and_scheme
from django.views.decorators.http import require_POST
from django.views.decorators.cache import never_cache
from core.access import role_required
from core.throttle import rate_limited
from .forms import (
    LoginForm,
    EmployerSignUpForm,
    JobSeekerSignUpForm,
    UserProfileForm,
    JobSeekerProfileForm,
    EmployerProfileForm,
)
from .models import Employer


@never_cache
def login_view(request):
    if request.user.is_authenticated:
        return redirect("dashboard:home")
    form = LoginForm(
        request.POST if request.method == "POST" else None, request=request
    )
    if request.method == "POST":
        if rate_limited(request, "login", 20):
            return render(
                request,
                "accounts/login.html",
                {"form": form, "throttled": True, "next": request.POST.get("next", "")},
                status=429,
            )
        if form.is_valid():
            login(request, form.user)
            request.session.set_expiry(
                settings.SESSION_COOKIE_AGE if form.cleaned_data["remember"] else 0
            )
            next_url = request.POST.get("next", "")
            if url_has_allowed_host_and_scheme(
                next_url,
                allowed_hosts={request.get_host()},
                require_https=request.is_secure(),
            ):
                return redirect(next_url)
            return redirect("dashboard:home")
    return render(
        request,
        "accounts/login.html",
        {"form": form, "next": request.GET.get("next", request.POST.get("next", ""))},
    )


@require_POST
def logout_view(request):
    logout(request)
    messages.success(request, "You have been signed out.")
    return redirect("jobs:home")


def signup_view(request):
    if request.user.is_authenticated:
        return redirect("dashboard:home")
    return render(request, "accounts/signup_choice.html")


def _signup(request, form_class, template):
    if request.user.is_authenticated:
        return redirect("dashboard:home")
    form = form_class(
        request.POST if request.method == "POST" else None, request.FILES or None
    )
    if request.method == "POST":
        if rate_limited(request, "signup", 10):
            form.add_error(None, "Too many attempts. Please try again in 15 minutes.")
            return render(request, template, {"form": form}, status=429)
        if form.is_valid():
            try:
                user = form.save()
            except ValidationError as error:
                form.add_error(None, error)
            except IntegrityError:
                form.add_error(
                    None,
                    "That account could not be created. Check that your username is still available and try again.",
                )
            else:
                login(request, user)
                request.session.set_expiry(0)
                messages.success(request, "Welcome to JOBLYFY. Your account is ready.")
                return redirect("dashboard:home")
    return render(request, template, {"form": form})


def employer_signup(request):
    return _signup(request, EmployerSignUpForm, "accounts/signup_employer.html")


def jobseeker_signup(request):
    return _signup(request, JobSeekerSignUpForm, "accounts/signup_jobseeker.html")


@role_required("jobseeker")
def user_profile(request):
    return _profile(
        request,
        JobSeekerProfileForm,
        request.user.jobseeker,
        "accounts/user_profile.html",
    )


@role_required("employer")
def employer_profile(request):
    return _profile(
        request,
        EmployerProfileForm,
        request.user.employer,
        "accounts/employer_profile.html",
    )


def _profile(request, form_class, profile, template):
    user_form = UserProfileForm(
        request.POST if request.method == "POST" else None,
        instance=request.user,
        prefix="user",
    )
    form = form_class(
        request.POST if request.method == "POST" else None,
        request.FILES or None,
        instance=profile,
        prefix="profile",
    )
    if request.method == "POST":
        # Serialize identity validation and writes with the configured SQLite
        # IMMEDIATE transaction; another profile/registration cannot claim the
        # same address between the check and the save.
        with transaction.atomic():
            valid_user, valid_profile = user_form.is_valid(), form.is_valid()
            if valid_user and valid_profile:
                user_form.save()
                form.save()
                messages.success(request, "Your profile has been updated.")
                return redirect(
                    "accounts:employer_profile"
                    if request.user.is_employer
                    else "accounts:user_profile"
                )
    return render(
        request, template, {"form": form, "user_form": user_form, "profile": profile}
    )


@role_required("jobseeker")
def own_resume(request):
    return private_file_response(request.user.jobseeker.resume)


def private_file_response(field):
    if not field or not field.storage.exists(field.name):
        raise Http404("No resume file is available. Please upload it again.")
    response = FileResponse(
        field.open("rb"),
        as_attachment=True,
        filename=Path(field.name).name,
        content_type="application/octet-stream",
    )
    response["Cache-Control"] = "private, no-store"
    response["X-Content-Type-Options"] = "nosniff"
    return response


def company_logo(request, pk):
    company = get_object_or_404(Employer, pk=pk, user__is_active=True)
    file = company.company_logo
    if not company.logo_available or Path(file.name).suffix.lower() not in {
        ".png",
        ".jpg",
        ".jpeg",
        ".webp",
    }:
        raise Http404
    response = FileResponse(
        file.open("rb"),
        content_type=mimetypes.guess_type(file.name)[0] or "application/octet-stream",
    )
    response["X-Content-Type-Options"] = "nosniff"
    return response


class PasswordResetView(auth_views.PasswordResetView):
    template_name = "accounts/password_reset.html"
    email_template_name = "accounts/password_reset_email.txt"
    subject_template_name = "accounts/password_reset_subject.txt"
    success_url = reverse_lazy("accounts:password_reset_done")

    def post(self, request, *args, **kwargs):
        if rate_limited(request, "password-reset", 5):
            form = self.get_form()
            form.add_error(None, "Too many requests. Please try again in 15 minutes.")
            return self.render_to_response(self.get_context_data(form=form), status=429)
        return super().post(request, *args, **kwargs)


@role_required("jobseeker")
def job_preferences(request):
    from .models import JobPreference
    from .forms import JobPreferenceForm
    from urllib.parse import urlencode

    preference = JobPreference.objects.filter(job_seeker=request.user.jobseeker).first()
    form = JobPreferenceForm(
        request.POST if request.method == "POST" else None, instance=preference
    )
    if request.method == "POST" and form.is_valid():
        preference = form.save(commit=False)
        preference.job_seeker = request.user.jobseeker
        preference.save()
        messages.success(
            request, "Job preferences saved. Your dashboard now uses these filters."
        )
        return redirect("accounts:job_preferences")
    return render(
        request,
        "accounts/preferences.html",
        {
            "form": form,
            "results_url": reverse_lazy("jobs:job_list")
            + "?"
            + urlencode(preference.search_params())
            if preference
            else reverse_lazy("jobs:job_list"),
        },
    )
