"""Private application drafts, review tokens and final backend validation."""

import json
from pathlib import Path
from uuid import uuid4
from django.contrib import messages
from django.core import signing
from django.core.exceptions import ValidationError
from django.core.files.base import ContentFile
from django.db import transaction
from django.http import Http404
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.views.decorators.http import require_GET, require_POST, require_http_methods
from core.access import role_required
from apps.accounts.validators import validate_resume
from apps.accounts.views import private_file_response
from apps.dashboard.models import Notification
from .models import Job, Application, ApplicationDraft, ScreeningAnswer
from .screening import (
    job_snapshot,
    fingerprint,
    evaluate_eligibility,
    evaluate_questions,
    combined_assessment,
)
from .screening_forms import (
    CandidateEligibilityForm,
    CandidateScreeningForm,
    ApplicationResumeForm,
    FinalSubmissionForm,
)

STEPS = [
    ("eligibility", "Eligibility"),
    ("questions", "Screening questions"),
    ("resume", "Resume & introduction"),
    ("review", "Review & submit"),
]
TOKEN_SALT = "joblyfy.application.review.v1"


def _job(job_id):
    job = get_object_or_404(
        Job.objects.select_related("employer__user", "category"), pk=job_id
    )
    if not job.is_open:
        raise Http404(
            "This job is not accepting applications. Your draft has not been submitted."
        )
    return job


def _config(job):
    rules, questions = (
        list(job.eligibility_rules.all()),
        list(job.screening_questions.all()),
    )
    snapshot = job_snapshot(job, rules, questions)
    return rules, questions, snapshot, fingerprint(snapshot)


def _draft(job, seeker):
    return ApplicationDraft.objects.filter(
        job=job, job_seeker=seeker
    ).first() or ApplicationDraft(job=job, job_seeker=seeker)


def _url(job, step="eligibility"):
    return reverse("jobs:application_start", args=[job.pk]) + "?step=" + step


def _form(step, job, rules, questions, draft, seeker, data=None, files=None):
    if step == "eligibility":
        initial = (
            draft.candidate_data
            if draft.pk
            else {"skills": seeker.skills[:2000], "work_location": seeker.location}
        )
        return CandidateEligibilityForm(data, job=job, rules=rules, initial=initial)
    if step == "questions":
        return CandidateScreeningForm(
            data, questions=questions, initial=draft.answers_data
        )
    if step == "resume":
        return ApplicationResumeForm(
            data,
            files,
            seeker=seeker,
            draft=draft,
            initial={"cover_letter": draft.cover_letter},
        )
    return None


def _report(job, rules, questions, draft):
    eligibility = evaluate_eligibility(job, rules, draft.candidate_data)
    screening = evaluate_questions(questions, draft.answers_data)
    return eligibility, screening, combined_assessment(eligibility, screening)


def _token(draft, digest):
    return signing.dumps(
        {
            "draft": draft.pk,
            "candidate": draft.job_seeker_id,
            "job": draft.job_id,
            "version": draft.version,
            "fingerprint": digest,
        },
        salt=TOKEN_SALT,
        compress=True,
    )


def _render(
    request,
    job,
    draft,
    step,
    form,
    rules,
    questions,
    digest,
    *,
    report=None,
    final_form=None,
    notice="",
    status=200,
):
    eligibility, screening, combined = _report(job, rules, questions, draft)
    if step == "review":
        report = combined
        final_form = final_form or FinalSubmissionForm(
            initial={"review_token": _token(draft, digest)}
        )
    steps = [
        {
            "key": key,
            "label": label,
            "number": i,
            "available": i <= draft.stage,
            "url": _url(job, key),
        }
        for i, (key, label) in enumerate(STEPS, 1)
    ]
    return render(
        request,
        "jobs/application_flow.html",
        {
            "job": job,
            "draft": draft,
            "step": step,
            "step_number": [v[0] for v in STEPS].index(step) + 1,
            "steps": steps,
            "form": form,
            "final_form": final_form,
            "report": report,
            "screening_report": screening,
            "notice": notice,
            "draft_version": draft.version if draft.pk else 0,
            "question_count": len(questions),
        },
        status=status,
    )


def _read_pdf(field):
    if not field or not field.storage.exists(field.name):
        raise ValidationError(
            "The selected resume is no longer available. Upload it again."
        )
    with field.open("rb") as source:
        content = source.read(5 * 1024 * 1024 + 1)
    validate_resume(ContentFile(content, name="resume.pdf"))
    return content


def _remove_after_commit(field, name):
    if name:
        transaction.on_commit(lambda: field.storage.delete(name))


@role_required("jobseeker")
@require_http_methods(["GET", "POST"])
def application_start(request, job_id):
    if request.method == "POST":
        # IMMEDIATE SQLite transactions reserve the writer before reading rules/drafts.
        with transaction.atomic():
            return _flow(request, job_id)
    return _flow(request, job_id)


def _flow(request, job_id):
    job, seeker = _job(job_id), request.user.jobseeker
    if job.is_demo and not job.accepts_demo_applications:
        messages.info(request, "Sample jobs do not accept applications.")
        return redirect(job)
    existing = Application.objects.filter(job=job, job_seeker=seeker).first()
    if existing:
        messages.info(
            request,
            "You already applied for this role. Your application is available below.",
        )
        return redirect("dashboard:application_detail", application_id=existing.pk)
    rules, questions, snapshot, digest = _config(job)
    draft = _draft(job, seeker)
    step = (
        request.POST.get("step", "eligibility")
        if request.method == "POST"
        else request.GET.get("step", "eligibility")
    )
    if step not in {v[0] for v in STEPS}:
        return redirect(_url(job))
    notice = ""
    if draft.pk and draft.rules_fingerprint != digest:
        notice = "The employer updated this job or its questions. Review your eligibility again; your previous answers and selected resume are retained for correction."
        if request.method == "POST" and step != "eligibility":
            messages.warning(request, notice)
            return redirect(_url(job))
        step = "eligibility"
    if [v[0] for v in STEPS].index(step) + 1 > draft.stage:
        return redirect(_url(job, STEPS[draft.stage - 1][0]))
    form = _form(
        step,
        job,
        rules,
        questions,
        draft,
        seeker,
        request.POST if request.method == "POST" else None,
        request.FILES or None,
    )
    report = (
        evaluate_eligibility(job, rules, draft.candidate_data)
        if step == "eligibility" and draft.pk
        else None
    )
    if request.method == "POST":
        if step == "review":
            return redirect(_url(job, "review"))
        if request.POST.get("draft_version") != str(draft.version if draft.pk else 0):
            return _render(
                request,
                job,
                draft,
                step,
                form,
                rules,
                questions,
                digest,
                notice="This draft changed in another window. Reload this page before continuing.",
                status=409,
            )
        if not form.is_valid():
            return _render(
                request,
                job,
                draft,
                step,
                form,
                rules,
                questions,
                digest,
                notice=notice,
                status=400,
            )
        if step == "eligibility":
            candidate = json.loads(json.dumps(form.cleaned_data, default=str))
            report = evaluate_eligibility(job, rules, candidate)
            draft.candidate_data, draft.rules_fingerprint, draft.stage = (
                candidate,
                digest,
                1,
            )
            draft.version += 1
            continuing = request.POST.get("action") == "continue"
            if continuing and report["can_continue"]:
                draft.stage = 2
            draft.save()
            if draft.stage == 2:
                return redirect(_url(job, "questions"))
            return _render(
                request,
                job,
                draft,
                step,
                form,
                rules,
                questions,
                digest,
                report=report,
                status=400 if continuing and not report["can_continue"] else 200,
            )
        if not evaluate_eligibility(job, rules, draft.candidate_data)["can_continue"]:
            messages.error(
                request, "Correct the blocking eligibility answers before continuing."
            )
            return redirect(_url(job))
        if step == "questions":
            report = evaluate_questions(questions, form.cleaned_data)
            if not report["can_continue"]:
                return _render(
                    request,
                    job,
                    draft,
                    step,
                    form,
                    rules,
                    questions,
                    digest,
                    report=report,
                    status=400,
                )
            draft.answers_data, draft.stage = form.cleaned_data, 3
            draft.version += 1
            draft.save()
            return redirect(_url(job, "resume"))
        if step == "resume":
            source = form.cleaned_data["resume_source"]
            old_name, new_name = draft.resume.name, None
            try:
                if source == "keep":
                    _read_pdf(draft.resume)
                else:
                    if source == "profile":
                        content, label = (
                            _read_pdf(seeker.resume),
                            "Saved profile resume",
                        )
                    else:
                        uploaded = form.cleaned_data["resume"]
                        uploaded.seek(0)
                        content, label = uploaded.read(), Path(uploaded.name).name[:150]
                    draft.resume.save(
                        f"{uuid4().hex}.pdf", ContentFile(content), save=False
                    )
                    new_name, draft.resume_label = draft.resume.name, label
                draft.cover_letter, draft.stage = form.cleaned_data["cover_letter"], 4
                draft.version += 1
                draft.save()
            except (ValidationError, OSError) as error:
                if new_name:
                    draft.resume.storage.delete(new_name)
                form.add_error(
                    "resume",
                    error
                    if isinstance(error, ValidationError)
                    else "The resume could not be stored. Please try again.",
                )
                return _render(
                    request,
                    job,
                    draft,
                    step,
                    form,
                    rules,
                    questions,
                    digest,
                    status=400,
                )
            except Exception:
                if new_name:
                    draft.resume.storage.delete(new_name)
                raise
            if new_name and old_name and old_name != new_name:
                _remove_after_commit(draft.resume, old_name)
            return redirect(_url(job, "review"))
    return _render(
        request,
        job,
        draft,
        step,
        form,
        rules,
        questions,
        digest,
        report=report,
        notice=notice,
    )


@role_required("jobseeker")
@require_POST
def apply_job(request, job_id):
    with transaction.atomic():
        job, seeker = _job(job_id), request.user.jobseeker
        if job.is_demo and not job.accepts_demo_applications:
            messages.info(
                request,
                "This is a sample listing, not a real vacancy. Applications are disabled.",
            )
            return redirect(job)
        existing = Application.objects.filter(job=job, job_seeker=seeker).first()
        if existing:
            messages.info(request, "You already have an application for this job.")
            return redirect("dashboard:application_detail", application_id=existing.pk)
        rules, questions, snapshot, digest = _config(job)
        draft, form = _draft(job, seeker), FinalSubmissionForm(request.POST)
        if not draft.pk or draft.stage != 4:
            return _render(
                request,
                job,
                draft,
                "eligibility",
                _form("eligibility", job, rules, questions, draft, seeker),
                rules,
                questions,
                digest,
                notice="Complete eligibility, screening questions and resume selection before submitting.",
                status=400,
            )
        valid = form.is_valid()
        if valid:
            try:
                payload = signing.loads(
                    form.cleaned_data["review_token"], salt=TOKEN_SALT, max_age=3600
                )
                expected = {
                    "draft": draft.pk,
                    "candidate": seeker.pk,
                    "job": job.pk,
                    "version": draft.version,
                    "fingerprint": digest,
                }
                valid = payload == expected and draft.rules_fingerprint == digest
            except signing.BadSignature:
                valid = False
            if not valid:
                form.add_error(
                    None,
                    "This review expired or the job/draft changed. Reopen eligibility and review your application again.",
                )
        ef = CandidateEligibilityForm(draft.candidate_data, job=job, rules=rules)
        sf = CandidateScreeningForm(draft.answers_data, questions=questions)
        if not ef.is_valid() or not sf.is_valid():
            valid = False
            form.add_error(
                None,
                "Some saved answers are incomplete or no longer valid. Correct them before submitting.",
            )
        eligibility, screening, combined = _report(job, rules, questions, draft)
        if not combined["can_continue"]:
            valid = False
            form.add_error(
                None,
                "The final backend check found a blocking requirement. Correct your answers before submitting.",
            )
        if not valid:
            return _render(
                request,
                job,
                draft,
                "review",
                None,
                rules,
                questions,
                digest,
                final_form=form,
                status=400,
            )
        try:
            content = _read_pdf(draft.resume)
        except (OSError, ValidationError):
            form.add_error(
                None,
                "The selected resume is missing or invalid. Return to Resume & introduction and select a valid PDF.",
            )
            return _render(
                request,
                job,
                draft,
                "review",
                None,
                rules,
                questions,
                digest,
                final_form=form,
                status=400,
            )
        application = Application.objects.create(
            job=job,
            job_seeker=seeker,
            cover_letter=draft.cover_letter,
            candidate_snapshot=draft.candidate_data,
            job_snapshot=snapshot,
            eligibility_snapshot={**combined, "eligibility": eligibility},
            screening_outcome=combined["outcome"],
        )
        new_name = None
        try:
            application.resume.save(
                f"{uuid4().hex}.pdf", ContentFile(content), save=False
            )
            new_name = application.resume.name
            application.save(update_fields=["resume"])
            ScreeningAnswer.objects.bulk_create(
                [
                    ScreeningAnswer(
                        application=application,
                        question_id=r["question_id"],
                        question_snapshot=r["question_snapshot"],
                        answer=r["answer"],
                        result=r["state"],
                        explanation=r["reason"],
                        position=r["position"],
                    )
                    for r in screening["rows"]
                ]
            )
            Notification.objects.create(
                recipient=job.employer.user,
                application=application,
                message=f"New {'practice ' if job.is_demo else ''}application for {job.title}."[
                    :400
                ],
            )
            old_field, old_name = draft.resume, draft.resume.name
            draft.delete()
            _remove_after_commit(old_field, old_name)
        except Exception:
            if new_name:
                application.resume.storage.delete(new_name)
            raise
    messages.success(
        request,
        "Practice application saved locally. This is not an application to a real employer."
        if job.is_demo
        else "Application submitted. Your answers, eligibility result and resume have been saved. Track status here.",
    )
    return redirect("dashboard:application_detail", application_id=application.pk)


@role_required("jobseeker")
@require_GET
def draft_resume(request, job_id):
    draft = get_object_or_404(
        ApplicationDraft, job_id=job_id, job_seeker=request.user.jobseeker
    )
    return private_file_response(draft.resume)


@role_required("jobseeker")
@require_POST
def discard_draft(request, job_id):
    with transaction.atomic():
        draft = get_object_or_404(
            ApplicationDraft, job_id=job_id, job_seeker=request.user.jobseeker
        )
        field, name = draft.resume, draft.resume.name
        draft.delete()
        _remove_after_commit(field, name)
    messages.success(
        request, "Your unfinished application and selected draft resume were removed."
    )
    return redirect("jobs:job_detail", job_id=job_id)
