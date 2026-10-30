from django.contrib import messages
from django.conf import settings
from django.contrib.auth.decorators import login_required
from django.core.paginator import Paginator
from django.db.models import Count, Q
from django.db import transaction
from .models import Notification
from .insights import application_insights
from apps.accounts.models import JobPreference
from apps.jobs.forms import JobSearchForm
from apps.jobs.search import search_jobs as filter_jobs
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone
from django.views.decorators.http import require_POST
from core.access import role_required
from apps.accounts.views import private_file_response
from apps.jobs.models import Job, Application, SavedJob, ApplicationDraft
from apps.jobs.forms import (
    CoverLetterForm,
    ApplicationStatusForm,
    ApplicationFilterForm,
)
from apps.jobs.views import with_company


@login_required
def home(request):
    if request.user.is_employer:
        return redirect("dashboard:employer_dashboard")
    if request.user.is_job_seeker:
        return redirect("dashboard:jobseeker_dashboard")
    return render(request, "dashboard/home.html")


def application_query():
    return Application.objects.select_related(
        "job__employer__user", "job__category", "job_seeker__user"
    )


@role_required("employer")
def employer_dashboard(request):
    employer = request.user.employer
    jobs = Job.objects.filter(employer=employer)
    applications = application_query().filter(job__employer=employer)
    stats, status_distribution = application_insights(applications)
    return render(
        request,
        "dashboard/employer_dashboard.html",
        {
            "stats": stats,
            "status_distribution": status_distribution,
            "total_jobs": jobs.count(),
            "active_jobs": jobs.open().count(),
            "recent_applications": applications[:5],
            "posted_jobs": jobs.annotate(application_count=Count("applications"))
            .select_related("employer__user", "category")
            .order_by("-posted_date", "-pk")[:5],
        },
    )


@role_required("jobseeker")
def job_seeker_dashboard(request):
    seeker = request.user.jobseeker
    applications = application_query().filter(job_seeker=seeker)
    stats, status_distribution = application_insights(applications)
    preference = JobPreference.objects.filter(job_seeker=seeker).first()
    recommended = with_company(Job.objects.open())
    preference_active = bool(preference and preference.search_params())
    if preference_active:
        filters = JobSearchForm(preference.search_params())
        recommended = (
            filter_jobs(recommended, filters.cleaned_data)
            if filters.is_valid()
            else recommended.none()
        )
    return render(
        request,
        "dashboard/job_seeker_dashboard.html",
        {
            "stats": stats,
            "profile": seeker,
            "status_distribution": status_distribution,
            "applications": applications[:5],
            "latest_jobs": recommended[:3],
            "preference_active": preference_active,
            "saved_count": SavedJob.objects.filter(job_seeker=seeker).count(),
            "drafts": ApplicationDraft.objects.filter(job_seeker=seeker)
            .select_related("job__employer__user")
            .order_by("-updated_at")[:5],
        },
    )


@role_required("employer")
def manage_jobs(request):
    jobs = (
        Job.objects.filter(employer=request.user.employer)
        .select_related("employer__user", "category")
        .annotate(application_count=Count("applications"))
        .order_by("-posted_date", "-pk")
    )
    state = request.GET.get("state", "")
    if state == "open":
        jobs = jobs.open()
    elif state == "inactive":
        jobs = jobs.filter(is_active=False)
    elif state == "expired":
        jobs = jobs.filter(
            is_active=True,
            publication_status="published",
            deadline__lt=timezone.localdate(),
        )
    elif state in {"draft", "paused", "closed"}:
        jobs = jobs.filter(publication_status=state)
    page = Paginator(jobs, 10).get_page(request.GET.get("page"))
    return render(
        request,
        "dashboard/manage_jobs.html",
        {"jobs": page, "page_obj": page, "state": state},
    )


@login_required
def applications(request):
    if request.user.is_employer:
        return redirect("dashboard:employer_applications")
    return seeker_applications(request)


@role_required("jobseeker")
def seeker_applications(request):
    return _applications(
        request, application_query().filter(job_seeker=request.user.jobseeker), False
    )


@role_required("employer")
def employer_applications(request):
    return _applications(
        request, application_query().filter(job__employer=request.user.employer), True
    )


def _applications(request, qs, employer):
    form = ApplicationFilterForm(
        request.GET or None, employer=request.user.employer if employer else None
    )
    if form.is_bound:
        if form.is_valid():
            data = form.cleaned_data
            if data["status"]:
                qs = qs.filter(status=data["status"])
            if data.get("screening"):
                qs = qs.filter(screening_outcome=data["screening"])
            if data.get("job"):
                qs = qs.filter(job=data["job"])
            if data["search"]:
                search = data["search"]
                qs = qs.filter(
                    Q(job__title__icontains=search)
                    | Q(job__employer__company_name__icontains=search)
                    | Q(job_seeker__user__first_name__icontains=search)
                    | Q(job_seeker__user__last_name__icontains=search)
                    | Q(job_seeker__user__username__icontains=search)
                )
        else:
            qs = qs.none()
    page = Paginator(qs, 10).get_page(request.GET.get("page"))
    return render(
        request,
        "dashboard/applications.html",
        {
            "applications": page,
            "page_obj": page,
            "employer_mode": employer,
            "form": form,
        },
    )


@role_required("employer")
def candidate_detail(request, application_id):
    application = get_object_or_404(
        application_query(), pk=application_id, job__employer=request.user.employer
    )
    return render(
        request,
        "dashboard/candidate_detail.html",
        {
            "application": application,
            "candidate": application.job_seeker,
            "status_form": ApplicationStatusForm(
                initial={"status": application.status}
            ),
        },
    )


@role_required("employer")
@require_POST
def manage_application(request, application_id):
    application = get_object_or_404(
        application_query(), pk=application_id, job__employer=request.user.employer
    )
    form = ApplicationStatusForm(request.POST)
    if not form.is_valid():
        return render(
            request,
            "dashboard/candidate_detail.html",
            {
                "application": application,
                "candidate": application.job_seeker,
                "status_form": form,
            },
            status=400,
        )
    new_status = form.cleaned_data["status"]
    with transaction.atomic():
        changed = (
            Application.objects.filter(pk=application.pk)
            .exclude(status__in=["withdrawn", new_status])
            .update(status=new_status, updated_date=timezone.now())
        )
        if changed:
            label = dict(Application.STATUS_CHOICES)[new_status]
            Notification.objects.create(
                recipient=application.job_seeker.user,
                application=application,
                message=f"Your application for {application.job.title} is now {label.lower()}."[
                    :400
                ],
            )
    if application.status == new_status:
        messages.info(request, "This application already has that status.")
        return redirect("dashboard:candidate_detail", application_id=application.pk)
    if changed:
        messages.success(request, "Application status updated.")
    else:
        messages.error(
            request, "A withdrawn application cannot be reopened by an employer."
        )
    return redirect("dashboard:candidate_detail", application_id=application.pk)


@role_required("jobseeker")
def edit_application(request, application_id):
    application = get_object_or_404(
        application_query(), pk=application_id, job_seeker=request.user.jobseeker
    )
    if not application.can_edit:
        messages.error(request, "Only pending applications to open jobs can be edited.")
        return redirect("dashboard:applications")
    form = CoverLetterForm(
        request.POST if request.method == "POST" else None, instance=application
    )
    if request.method == "POST" and form.is_valid():
        changed = Application.objects.filter(
            pk=application.pk, status="pending"
        ).update(
            cover_letter=form.cleaned_data["cover_letter"], updated_date=timezone.now()
        )
        if changed:
            messages.success(request, "Your cover letter has been updated.")
        else:
            messages.error(
                request, "This application has changed and can no longer be edited."
            )
        return redirect("dashboard:applications")
    return render(
        request,
        "dashboard/edit_application.html",
        {"form": form, "application": application},
    )


@role_required("jobseeker")
@require_POST
def withdraw_application(request, application_id):
    application = get_object_or_404(
        Application, pk=application_id, job_seeker=request.user.jobseeker
    )
    with transaction.atomic():
        changed = Application.objects.filter(
            pk=application.pk,
            status__in=["pending", "reviewing", "shortlisted", "interview"],
        ).update(status="withdrawn", updated_date=timezone.now())
        if changed:
            Notification.objects.create(
                recipient=application.job.employer.user,
                application=application,
                message=f"An application for {application.job.title} was withdrawn."[
                    :400
                ],
            )
    if changed:
        messages.success(request, "Application withdrawn. It remains in your history.")
    else:
        messages.error(
            request, "This application cannot be withdrawn at its current stage."
        )
    return redirect("dashboard:applications")


@login_required
def application_resume(request, application_id):
    qs = application_query()
    if request.user.is_employer and hasattr(request.user, "employer"):
        qs = qs.filter(job__employer=request.user.employer).exclude(status="withdrawn")
    elif request.user.is_job_seeker and hasattr(request.user, "jobseeker"):
        qs = qs.filter(job_seeker=request.user.jobseeker)
    else:
        qs = qs.none()
    application = get_object_or_404(qs, pk=application_id)
    return private_file_response(application.resume or application.job_seeker.resume)


@role_required("jobseeker")
def saved_jobs(request):
    saved = SavedJob.objects.filter(job_seeker=request.user.jobseeker).select_related(
        "job__employer__user", "job__category"
    )
    if not settings.DEBUG:
        saved = saved.filter(job__is_demo=False)
    page = Paginator(saved, 9).get_page(request.GET.get("page"))
    return render(
        request, "dashboard/saved_jobs.html", {"saved_jobs": page, "page_obj": page}
    )


@login_required
def notifications(request):
    qs = Notification.objects.filter(recipient=request.user).select_related("recipient")
    page = Paginator(qs, 15).get_page(request.GET.get("page"))
    return render(
        request,
        "dashboard/notifications.html",
        {"notifications": page, "page_obj": page},
    )


@login_required
@require_POST
def read_notification(request, pk):
    note = get_object_or_404(Notification, pk=pk, recipient=request.user)
    Notification.objects.filter(pk=note.pk, read_at__isnull=True).update(
        read_at=timezone.now()
    )
    return redirect(note.get_absolute_url())


@login_required
@require_POST
def read_all_notifications(request):
    Notification.objects.filter(recipient=request.user, read_at__isnull=True).update(
        read_at=timezone.now()
    )
    messages.success(request, "All updates marked as read.")
    return redirect("dashboard:notifications")


@role_required("jobseeker")
def application_detail(request, application_id):
    application = get_object_or_404(
        application_query(), pk=application_id, job_seeker=request.user.jobseeker
    )
    return render(
        request, "dashboard/application_detail.html", {"application": application}
    )
