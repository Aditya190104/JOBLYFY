"""Owned job editing and per-job screening configuration."""

from django.contrib import messages
from django.db import transaction
from django.db.models import F
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone
from django.views.decorators.http import require_POST
from core.access import role_required
from .models import Job
from .forms import JobForm
from .screening_forms import EligibilitySettingsForm, ScreeningQuestionFormSet


def job_editor(request, job=None):
    if request.method == "POST":
        with transaction.atomic():
            if job:
                job = get_object_or_404(
                    Job.objects.select_for_update(),
                    pk=job.pk,
                    employer=request.user.employer,
                )
            return _editor(request, job)
    return _editor(request, job)


def _editor(request, job):
    data = request.POST if request.method == "POST" else None
    form = JobForm(data, instance=job)
    rules_form = EligibilitySettingsForm(data, job=job, prefix="rules")
    if data is not None:
        valid, rules_valid = form.is_valid(), rules_form.is_valid()
        if valid and rules_valid:
            instance = form.save(commit=False)
            if job and form.cleaned_data.get("edit_revision") not in (
                None,
                job.screening_revision,
            ):
                form.add_error(
                    None, "This job changed in another window. Reload before saving."
                )
            elif rules_form.validate_job(instance):
                instance.employer = request.user.employer
                instance.is_demo = request.user.employer.is_demo
                instance.is_active = instance.publication_status == "published"
                instance.screening_revision += 1
                instance.save()
                rules_form.save(instance)
                messages.success(
                    request,
                    f"Job saved as {instance.get_publication_status_display().lower()}. Configure screening questions from Manage jobs.",
                )
                return redirect("dashboard:manage_jobs")
    groups = [
        ("The opportunity", ["title", "category", "description", "responsibilities"]),
        (
            "Qualifications & skills",
            [
                "qualifications",
                "requirements",
                "mandatory_skills",
                "preferred_skills",
                "experience_level",
                "min_experience",
                "max_experience",
            ],
        ),
        (
            "Work & compensation",
            [
                "location",
                "work_mode",
                "job_type",
                "salary",
                "salary_min",
                "salary_max",
                "benefits",
                "latitude",
                "longitude",
            ],
        ),
        (
            "Application details",
            ["deadline", "application_instructions", "publication_status"],
        ),
    ]
    return render(
        request,
        "jobs/post_job.html",
        {
            "form": form,
            "job": job,
            "rules_form": rules_form,
            "field_groups": [
                (title, [form[name] for name in names]) for title, names in groups
            ],
        },
    )


@role_required("employer")
@require_POST
def change_job_status(request, job_id):
    with transaction.atomic():
        job = get_object_or_404(
            Job.objects.select_for_update(), pk=job_id, employer=request.user.employer
        )
        status = request.POST.get("status")
        if status not in dict(Job.PUBLICATION_CHOICES):
            messages.error(request, "Choose a valid job status.")
            return redirect("dashboard:manage_jobs")
        if status == "published":
            if job.deadline and job.deadline < timezone.localdate():
                messages.error(
                    request,
                    "Update the application deadline before publishing this job.",
                )
                return redirect("jobs:edit_job", job_id=job.pk)
            if not all(
                [
                    job.title.strip(),
                    job.description.strip(),
                    job.requirements.strip(),
                    job.location.strip(),
                    job.job_type,
                ]
            ):
                messages.error(
                    request,
                    "Complete the job description, requirements and workplace details before publishing.",
                )
                return redirect("jobs:edit_job", job_id=job.pk)
        job.publication_status, job.is_active = status, status == "published"
        job.screening_revision += 1
        job.save(
            update_fields=["publication_status", "is_active", "screening_revision"]
        )
        messages.success(
            request,
            f"Job {job.get_publication_status_display().lower()}. Existing applications are retained.",
        )
    return redirect("dashboard:manage_jobs")


@role_required("employer")
@require_POST
def toggle_job(request, job_id):
    with transaction.atomic():
        job = get_object_or_404(
            Job.objects.select_for_update(), pk=job_id, employer=request.user.employer
        )
        activate = not (job.is_active and job.publication_status == "published")
        if activate and job.deadline and job.deadline < timezone.localdate():
            messages.error(
                request, "Update the application deadline before reactivating this job."
            )
        elif activate and job.publication_status in {"draft", "closed"}:
            messages.info(
                request, "Use Publish to publish a draft or reopen a closed role."
            )
        else:
            job.publication_status = "published" if activate else "paused"
            job.is_active = activate
            job.screening_revision += 1
            job.save(
                update_fields=["publication_status", "is_active", "screening_revision"]
            )
            messages.success(
                request,
                "Job published."
                if activate
                else "Job paused. Existing applications remain available.",
            )
    return redirect("dashboard:manage_jobs")


@role_required("employer")
def screening_questions(request, job_id):
    if request.method == "POST":
        with transaction.atomic():
            return _questions(request, job_id)
    return _questions(request, job_id)


def _questions(request, job_id):
    job = get_object_or_404(Job, pk=job_id, employer=request.user.employer)
    data = request.POST if request.method == "POST" else None
    formset = ScreeningQuestionFormSet(data, instance=job, prefix="questions")
    revision_error = ""
    if data is not None:
        valid = formset.is_valid()
        if request.POST.get("revision") != str(job.screening_revision):
            revision_error = (
                "The job or questions changed. Reload the page before saving."
            )
        elif valid:
            formset.save()
            Job.objects.filter(pk=job.pk).update(
                screening_revision=F("screening_revision") + 1
            )
            messages.success(
                request,
                "Screening questions saved. Submitted answers keep their original question and rule snapshots.",
            )
            return redirect("jobs:screening_questions", job_id=job.pk)
    return render(
        request,
        "jobs/screening_questions.html",
        {"job": job, "formset": formset, "revision_error": revision_error},
    )
