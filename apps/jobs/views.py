from django.contrib import messages
from django.core.paginator import Paginator
from django.db import transaction
from django.db.models import Q, Count, Avg, Min, Max
from django.conf import settings
from django.utils.http import url_has_allowed_host_and_scheme
from django.http import JsonResponse
from django.views.decorators.http import require_GET
from core.throttle import rate_limited
from .locations import cities, key, location_query, normalize_location
from .search import search_jobs as filter_jobs
from django.http import Http404
from django.shortcuts import render, redirect, get_object_or_404
from django.utils import timezone
from django.views.decorators.http import require_POST
from core.access import role_required
from apps.accounts.models import Employer
from .forms import JobApplicationForm, JobSearchForm, CompanyReviewForm
from .models import Job, Application, Category, SavedJob, CompanyReview


def with_company(qs):
    return qs.select_related("employer__user", "category")


def open_filter(prefix="jobs__"):
    return (
        Q(
            **{prefix + "is_active": True, prefix + "employer__user__is_active": True},
        )
        & Q(**{prefix + "publication_status": "published"})
        & (Q() if settings.DEBUG else Q(**{prefix + "is_demo": False}))
        & (
            Q(**{prefix + "deadline__isnull": True})
            | Q(**{prefix + "deadline__gte": timezone.localdate()})
        )
    )


def categories_query():
    return Category.objects.annotate(
        open_count=Count("job", filter=open_filter("job__"))
    ).order_by("name")


def companies_query():
    return (
        Employer.objects.filter(user__is_active=True)
        .filter(Q() if settings.DEBUG else Q(is_demo=False))
        .select_related("user")
        .annotate(
            open_count=Count("jobs", filter=open_filter(), distinct=True),
            review_count=Count(
                "reviews",
                filter=Q(
                    reviews__status="approved", reviews__author__user__is_active=True
                ),
                distinct=True,
            ),
            average_rating=Avg(
                "reviews__rating",
                filter=Q(
                    reviews__status="approved", reviews__author__user__is_active=True
                ),
            ),
        )
        .order_by("company_name")
    )


def home(request):
    jobs = Job.objects.open()
    return render(
        request,
        "jobs/home.html",
        {
            "featured_jobs": with_company(jobs.filter(is_featured=True))[:3],
            "recent_jobs": with_company(jobs)[:6],
            "categories": categories_query().order_by("-open_count", "name")[:8],
            "companies": companies_query()[:4],
            "job_count": jobs.filter(is_demo=False).count(),
            "listing_count": jobs.count(),
            "sample_job_count": jobs.filter(is_demo=True).count(),
            "company_count": Employer.objects.filter(
                user__is_active=True, is_demo=False
            ).count(),
            "category_count": Category.objects.count(),
        },
    )


def job_list(request):
    form = JobSearchForm(request.GET or None)
    jobs = with_company(Job.objects.open())
    data = {}
    if form.is_bound:
        if form.is_valid():
            data = form.cleaned_data
            jobs = filter_jobs(jobs, data)
        else:
            jobs = jobs.none()
    page = Paginator(jobs, 9).get_page(request.GET.get("page"))
    page_jobs = list(page.object_list)
    saved_ids = set()
    if (
        request.user.is_authenticated
        and request.user.is_job_seeker
        and hasattr(request.user, "jobseeker")
    ):
        saved_ids = set(
            SavedJob.objects.filter(
                job_seeker=request.user.jobseeker, job_id__in=[j.pk for j in page_jobs]
            ).values_list("job_id", flat=True)
        )
    selected = next(
        (job for job in page_jobs if str(job.pk) == request.GET.get("selected")),
        page_jobs[0] if page_jobs else None,
    )
    chips = []
    for name, field in form.fields.items():
        raw = request.GET.get(name)
        if not raw or name == "sort":
            continue
        params = request.GET.copy()
        for remove in [name, "page", "selected"]:
            params.pop(remove, None)
        if name == "location":
            params.pop("radius", None)
        label = str(data.get(name) if data.get(name) is not None else raw[:100])
        if getattr(field, "choices", None) and name not in {"category", "company"}:
            label = dict(field.choices).get(raw, label)
        chips.append(
            {
                "label": f"{field.label or name.replace('_', ' ').title()}: {label}",
                "url": "?" + params.urlencode(),
            }
        )
    return render(
        request,
        "jobs/job_list.html",
        {
            "jobs": page_jobs,
            "page_obj": page,
            "form": form,
            "saved_ids": saved_ids,
            "selected_job": selected,
            "filter_chips": chips,
            "filter_fields": [
                form[name]
                for name in [
                    "work_mode",
                    "job_type",
                    "radius",
                    "category",
                    "experience",
                    "posted",
                    "company",
                    "min_salary",
                    "max_salary",
                ]
            ],
            "radius_search": bool(
                data.get("radius") and data.get("work_mode") != "remote"
            ),
            "remote_search": data.get("work_mode") == "remote",
            "salary_filter": data.get("min_salary") is not None
            or data.get("max_salary") is not None,
        },
    )


@require_GET
def location_suggestions(request):
    query = " ".join(request.GET.get("q", "").split())
    if len(query) > 100:
        return JsonResponse(
            {"error": "Use 100 characters or fewer.", "results": []}, status=400
        )
    needle = key(query)
    matches = [
        city
        for city in cities()
        if not needle
        or any(
            needle in key(v)
            for v in city["aliases"]
            + [city["state"], city["name"] + " " + city["state"]]
        )
    ][:7]
    jobs = Job.objects.open()
    results = [
        {
            "value": c["name"],
            "label": f"{c['name']}, {c['state']}",
            "count": jobs.filter(location_query(c["name"])).count(),
            "kind": "city",
        }
        for c in matches
    ]
    if query:
        # Bounded distinct query supplements the offline catalog with employer-entered locations.
        values = (
            jobs.filter(location__icontains=query)
            .order_by("location")
            .values_list("location", flat=True)
            .distinct()[:8]
        )
        existing = {key(row["value"]) for row in results}
        for value in values:
            normalized = normalize_location(value)
            if key(normalized) not in existing and len(results) < 8:
                results.append(
                    {
                        "value": normalized,
                        "label": value,
                        "count": jobs.filter(location_query(normalized)).count(),
                        "kind": "job_location",
                    }
                )
                existing.add(key(normalized))
    if (not needle or needle in "remote work from home") and len(results) < 8:
        results.append(
            {
                "value": "Remote",
                "label": "Remote — work from anywhere allowed by the employer",
                "count": jobs.filter(work_mode="remote").count(),
                "kind": "remote",
            }
        )
    return JsonResponse(
        {
            "results": results,
            "count_label": "open listings (including labelled samples in development)",
        }
    )


# One implementation avoids divergent filtering and missing-template paths.
search_jobs = job_list


def job_detail_context(request, job, form=None):
    application = None
    saved = False
    if (
        request.user.is_authenticated
        and request.user.is_job_seeker
        and hasattr(request.user, "jobseeker")
    ):
        application = Application.objects.filter(
            job=job, job_seeker=request.user.jobseeker
        ).first()
        saved = SavedJob.objects.filter(
            job=job, job_seeker=request.user.jobseeker
        ).exists()
        form = form or JobApplicationForm(seeker=request.user.jobseeker)
    return {
        "job": job,
        "application": application,
        "has_applied": application is not None,
        "saved": saved,
        "application_form": form,
        "related_jobs": with_company(
            Job.objects.open().filter(category=job.category).exclude(pk=job.pk)
        )[:3],
    }


def job_detail(request, job_id):
    job = get_object_or_404(with_company(Job.objects.all()), pk=job_id)
    if job.is_demo and not settings.DEBUG:
        raise Http404
    context = job_detail_context(request, job)
    owner = request.user.is_authenticated and job.employer.user_id == request.user.pk
    if (
        (
            not job.is_active
            or job.publication_status != "published"
            or not job.employer.user.is_active
        )
        and not owner
        and not context["application"]
    ):
        raise Http404
    return render(request, "jobs/job_detail.html", context)


@role_required("employer")
def post_job(request):
    return _job_editor(request)


@role_required("employer")
def edit_job(request, job_id):
    job = get_object_or_404(Job, pk=job_id, employer=request.user.employer)
    return _job_editor(request, job)


def _job_editor(request, job=None):
    from .job_management import job_editor

    return job_editor(request, job)


# Existing URL names now delegate to the reviewed workflow.
from .job_management import toggle_job as toggle_job
from .application_views import apply_job as apply_job


@role_required("jobseeker")
@require_POST
def save_job(request, job_id):
    wants_json = request.headers.get("Accept") == "application/json"
    intent = request.POST.get("intent", "")
    if intent not in {"", "save", "remove"} or (wants_json and not intent):
        return JsonResponse({"error": "Choose save or remove."}, status=400)
    with transaction.atomic():
        job = get_object_or_404(with_company(Job.objects.all()), pk=job_id)
        saved = SavedJob.objects.filter(job=job, job_seeker=request.user.jobseeker)
        is_saved = saved.exists()
        remove = intent == "remove" or (not intent and is_saved)
        if remove:
            saved.delete()
            is_saved = False
            message = "Job removed from your saved list."
        elif is_saved or job.is_open:
            SavedJob.objects.get_or_create(job=job, job_seeker=request.user.jobseeker)
            is_saved = True
            message = "Job saved for later."
        else:
            message = "This job is no longer accepting applications."
            if wants_json:
                return JsonResponse({"error": message, "saved": False}, status=409)
        if wants_json:
            return JsonResponse({"job_id": job.pk, "saved": is_saved, "message": message})
    if is_saved or remove:
        messages.success(request, message)
    else:
        messages.info(request, message)
    next_url = request.POST.get("next", "")
    if url_has_allowed_host_and_scheme(
        next_url, allowed_hosts={request.get_host()}, require_https=request.is_secure()
    ):
        return redirect(next_url)
    return redirect("dashboard:saved_jobs")


def categories(request):
    return render(request, "jobs/categories.html", {"categories": categories_query()})


def category_detail(request, pk):
    category = get_object_or_404(Category, pk=pk)
    jobs = Paginator(
        with_company(Job.objects.open().filter(category=category)), 9
    ).get_page(request.GET.get("page"))
    return render(
        request,
        "jobs/category_detail.html",
        {"category": category, "jobs": jobs, "page_obj": jobs},
    )


def companies(request):
    query = request.GET.get("search", "")[:150]
    qs = companies_query()
    if query:
        qs = qs.filter(
            Q(company_name__icontains=query)
            | Q(industry__icontains=query)
            | Q(location__icontains=query)
        )
    page = Paginator(qs, 12).get_page(request.GET.get("page"))
    return render(
        request,
        "jobs/companies.html",
        {"companies": page, "page_obj": page, "search": query},
    )


def company_detail(request, pk):
    company = get_object_or_404(companies_query(), pk=pk)
    jobs = Paginator(
        with_company(Job.objects.open().filter(employer=company)), 9
    ).get_page(request.GET.get("page"))
    return render(
        request,
        "jobs/company_detail.html",
        {
            "company": company,
            "active_jobs": jobs,
            "page_obj": jobs,
            "reviews": Paginator(
                CompanyReview.objects.filter(
                    employer=company, status="approved", author__user__is_active=True
                ),
                5,
            ).get_page(request.GET.get("review_page")),
            "own_review": CompanyReview.objects.filter(
                employer=company, author__user=request.user
            ).first()
            if request.user.is_authenticated and request.user.is_job_seeker
            else None,
            "salary_insights": Job.objects.open()
            .filter(
                employer=company,
                is_demo=False,
                salary_min__isnull=False,
                salary_max__isnull=False,
            )
            .aggregate(
                count=Count("pk"), low=Min("salary_min"), high=Max("salary_max")
            ),
        },
    )


def about(request):
    return render(request, "jobs/about.html")


@role_required("jobseeker")
def company_review(request, pk):
    company = get_object_or_404(Employer, pk=pk, user__is_active=True, is_demo=False)
    seeker = request.user.jobseeker
    review = CompanyReview.objects.filter(employer=company, author=seeker).first()
    form = CompanyReviewForm(
        request.POST if request.method == "POST" else None, instance=review
    )
    if request.method == "POST":
        if rate_limited(request, "review", 10):
            form.add_error(
                None, "Too many submissions. Please try again in 15 minutes."
            )
            return render(
                request,
                "jobs/company_review.html",
                {"company": company, "form": form},
                status=429,
            )
        if form.is_valid():
            with transaction.atomic():
                CompanyReview.objects.update_or_create(
                    employer=company,
                    author=seeker,
                    defaults={
                        **{
                            k: form.cleaned_data[k]
                            for k in ["rating", "relationship", "title", "body"]
                        },
                        "status": "pending",
                        "moderated_at": None,
                    },
                )
            messages.success(
                request,
                "Your review is pending moderation. Editing a published review sends it back for moderation.",
            )
            return redirect(company)
    return render(
        request, "jobs/company_review.html", {"company": company, "form": form}
    )


@role_required("jobseeker")
@require_POST
def remove_review(request, pk):
    review = get_object_or_404(CompanyReview, pk=pk, author=request.user.jobseeker)
    company = review.employer
    review.delete()
    messages.success(request, "Your review was removed.")
    return redirect(company)
