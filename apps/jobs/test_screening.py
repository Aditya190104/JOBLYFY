"""Regression coverage for recruiter rules, candidate screening and private evidence."""

from datetime import timedelta
from decimal import Decimal
from io import StringIO
from unittest.mock import patch
from django.core import signing
from django.core.exceptions import ValidationError
from django.core.management import call_command
from django.db import IntegrityError, transaction
from django.test import Client
from django.urls import reverse
from django.utils import timezone
from core.test_support import PortalTestCase, pdf_upload
from apps.dashboard.models import Notification
from .models import (
    Job,
    Application,
    ApplicationDraft,
    EligibilityRule,
    ScreeningQuestion,
    ScreeningAnswer,
)
from .screening import (
    evaluate_eligibility,
    evaluate_questions,
    job_snapshot,
    fingerprint,
)
from .screening_forms import (
    CandidateEligibilityForm,
    CandidateScreeningForm,
    ScreeningQuestionForm,
)
from .application_views import TOKEN_SALT


class ScreeningTests(PortalTestCase):
    def configure(self, blocking=True):
        self.job.responsibilities = "Build accessible applications."
        self.job.qualifications = "B.Tech or B.E."
        self.job.mandatory_skills, self.job.preferred_skills = (
            "Python, Django",
            "Docker, Redis",
        )
        self.job.min_experience, self.job.max_experience = Decimal(1), Decimal(5)
        self.job.application_instructions = "Describe a project."
        self.job.save()
        for kind, values in [
            ("qualification", ["B.Tech", "B.E."]),
            ("experience", []),
            ("skills", []),
            ("location", ["Mohali"]),
            ("work_arrangement", []),
        ]:
            EligibilityRule.objects.update_or_create(
                job=self.job,
                kind=kind,
                defaults={
                    "values": values,
                    "is_blocking": blocking,
                    "allow_relocation": kind == "location",
                },
            )
        return list(self.job.eligibility_rules.all())

    def good(self, **overrides):
        return {
            "qualification": " B.Tech ",
            "years_experience": "2.5",
            "skills": "python, DJANGO",
            "work_location": "SAS Nagar",
            "relocate": "no",
            "work_arrangement": "yes",
            **overrides,
        }

    def question(self, **overrides):
        return ScreeningQuestion.objects.create(
            **{
                "job": self.job,
                "prompt": "Can you attend agreed team sessions?",
                "kind": "yes_no",
                "required": True,
                "match_mode": "any",
                "expected_answers": ["yes"],
                "is_blocking": True,
                **overrides,
            }
        )

    def editor(self, **overrides):
        return {
            "title": "Full-stack engineer",
            "category": self.category.pk,
            "description": "Build useful software.",
            "requirements": "Communicate clearly.",
            "location": "Mohali",
            "job_type": "full_time",
            "experience_level": "entry",
            "work_mode": "hybrid",
            "publication_status": "draft",
            "responsibilities": "Ship accessible features.",
            "qualifications": "B.Tech",
            "mandatory_skills": "Python, Django",
            "preferred_skills": "Docker",
            "min_experience": "1",
            "max_experience": "5",
            "salary_min": "600000",
            "salary_max": "900000",
            "application_instructions": "Explain a project.",
            "rules-accepted_qualifications": "B.Tech, B.E.",
            "rules-block_qualification": "on",
            "rules-block_skills": "on",
            "rules-allowed_locations": "Mohali, Chandigarh",
            "rules-allow_relocation": "on",
            "rules-check_work_arrangement": "on",
            **overrides,
        }

    def flow(self, step, data=None):
        draft = ApplicationDraft.objects.filter(
            job=self.job, job_seeker=self.seeker
        ).first()
        return self.client.post(
            reverse("jobs:application_start", args=[self.job.pk]),
            {
                "step": step,
                "draft_version": draft.version if draft else 0,
                **(data or {}),
            },
        )

    def final(self, review, **overrides):
        return self.client.post(
            reverse("jobs:apply_job", args=[self.job.pk]),
            {
                "consent": "on",
                "review_token": review.context["final_form"].initial["review_token"],
                **overrides,
            },
        )

    def qdata(self, q=None, **overrides):
        return {
            "revision": self.job.screening_revision,
            "questions-TOTAL_FORMS": 1,
            "questions-INITIAL_FORMS": 1 if q else 0,
            "questions-MIN_NUM_FORMS": 0,
            "questions-MAX_NUM_FORMS": 20,
            "questions-0-id": q.pk if q else "",
            "questions-0-prompt": "Which tools?",
            "questions-0-kind": "multiple",
            "questions-0-options": "Git\nDocker\nLinux",
            "questions-0-required": "on",
            "questions-0-position": 1,
            "questions-0-match_mode": "all",
            "questions-0-expected_answers": "Git\nLinux",
            "questions-0-is_blocking": "on",
            **overrides,
        }

    def test_create_structured_draft_and_rules(self):
        self.login_employer()
        self.assertEqual(
            self.client.post(reverse("jobs:post_job"), self.editor()).status_code, 302
        )
        job = Job.objects.get(title="Full-stack engineer")
        self.assertEqual(job.publication_status, "draft")
        self.assertFalse(job.is_active)
        self.assertEqual(job.eligibility_rules.count(), 5)
        self.assertEqual(job.responsibilities, "Ship accessible features.")
        self.assertEqual(job.salary_min, 600000)

    def test_publish_pause_close_preserves_applications(self):
        app = Application.objects.create(job=self.job, job_seeker=self.seeker)
        self.login_employer()
        for state, visible in [
            ("paused", False),
            ("published", True),
            ("closed", False),
            ("draft", False),
        ]:
            self.client.post(
                reverse("jobs:change_job_status", args=[self.job.pk]), {"status": state}
            )
            self.job.refresh_from_db()
            self.assertEqual(self.job.is_open, visible)
            self.assertEqual(
                Job.objects.open().filter(pk=self.job.pk).exists(), visible
            )
            self.assertTrue(Application.objects.filter(pk=app.pk).exists())

    def test_drafts_hidden_in_public_counts_and_routes(self):
        self.job.publication_status = "draft"
        self.job.save()
        self.assertEqual(self.client.get(reverse("jobs:home")).context["job_count"], 0)
        self.assertEqual(
            self.client.get(reverse("jobs:job_list"))
            .context["page_obj"]
            .paginator.count,
            0,
        )
        self.assertEqual(self.client.get(self.job.get_absolute_url()).status_code, 404)
        self.login_seeker()
        self.assertEqual(
            self.client.get(
                reverse("jobs:application_start", args=[self.job.pk])
            ).status_code,
            404,
        )
        self.login_employer()
        self.assertEqual(self.client.get(self.job.get_absolute_url()).status_code, 200)

    def test_job_owner_role_and_csrf(self):
        url = reverse("jobs:change_job_status", args=[self.job.pk])
        self.login_seeker()
        self.assertEqual(self.client.post(url, {"status": "closed"}).status_code, 403)
        self.client.force_login(self.other_employer_user)
        for name in ("edit_job", "screening_questions"):
            self.assertEqual(
                self.client.get(
                    reverse("jobs:" + name, args=[self.job.pk])
                ).status_code,
                404,
            )
        self.assertEqual(self.client.post(url, {"status": "closed"}).status_code, 404)
        self.login_employer()
        self.assertEqual(self.client.get(url).status_code, 405)
        strict = Client(enforce_csrf_checks=True)
        strict.force_login(self.employer_user)
        self.assertEqual(strict.post(url, {"status": "closed"}).status_code, 403)

    def test_structured_job_and_rules_validation(self):
        self.login_employer()
        for change in [
            {"min_experience": 8, "max_experience": 3},
            {"salary_min": 900000, "salary_max": 600000},
            {"rules-accepted_qualifications": ""},
            {"mandatory_skills": ""},
            {
                "min_experience": "",
                "max_experience": "",
                "rules-block_experience": "on",
            },
            {"rules-allowed_locations": ""},
            {"rules-check_work_arrangement": "", "rules-block_work_arrangement": "on"},
        ]:
            r = self.client.post(reverse("jobs:post_job"), self.editor(**change))
            self.assertTrue(
                r.context["form"].errors or r.context["rules_form"].errors, change
            )
            self.assertEqual(Job.objects.count(), 1)

    def test_edit_does_not_accept_forged_company_or_stale_revision(self):
        self.login_employer()
        url = reverse("jobs:edit_job", args=[self.job.pk])
        self.client.post(
            url,
            self.editor(
                employer=self.other_employer.pk,
                publication_status="published",
                edit_revision=1,
            ),
        )
        self.job.refresh_from_db()
        self.assertEqual(self.job.employer_id, self.employer.pk)
        self.assertContains(
            self.client.get(self.job.get_absolute_url()), "Responsibilities"
        )
        self.assertTrue(
            self.client.post(url, self.editor(edit_revision=1))
            .context["form"]
            .non_field_errors()
        )

    def test_publishing_expired_or_incomplete_job_fails(self):
        self.login_employer()
        self.job.publication_status, self.job.is_active = "closed", False
        self.job.deadline = timezone.localdate() - timedelta(days=1)
        self.job.save()
        url = reverse("jobs:change_job_status", args=[self.job.pk])
        self.client.post(url, {"status": "published"})
        self.job.refresh_from_db()
        self.assertFalse(self.job.is_active)
        self.job.deadline, self.job.description = None, ""
        self.job.save()
        self.client.post(url, {"status": "published"})
        self.job.refresh_from_db()
        self.assertFalse(self.job.is_active)

    def test_eligible_ineligible_and_unknown_are_distinct(self):
        rules = self.configure()
        good = evaluate_eligibility(self.job, rules, self.good())
        self.assertEqual(good["outcome"], "met")
        self.assertTrue(all(r["state"] == "met" for r in good["rows"]))
        bad = evaluate_eligibility(
            self.job, rules, self.good(skills="Python", years_experience="0")
        )
        self.assertEqual(bad["outcome"], "blocked")
        unknown = evaluate_eligibility(self.job, rules, {})
        self.assertFalse(unknown["can_continue"])
        self.assertTrue(all(r["state"] == "unknown" for r in unknown["rows"]))

    def test_preferred_skills_never_reject(self):
        report = evaluate_eligibility(self.job, self.configure(), self.good())
        self.assertEqual(report["outcome"], "met")
        self.assertFalse(any(r["met"] for r in report["recommendations"]))
        self.assertIn("not a verification", report["disclaimer"])

    def test_exact_skills_do_not_confuse_java_with_javascript(self):
        self.configure()
        self.job.mandatory_skills = "Java, C++"
        rules = list(self.job.eligibility_rules.filter(kind="skills"))
        self.assertEqual(
            evaluate_eligibility(self.job, rules, {"skills": "JavaScript, C"})[
                "outcome"
            ],
            "blocked",
        )
        self.assertEqual(
            evaluate_eligibility(self.job, rules, {"skills": " java , c++ "})[
                "outcome"
            ],
            "met",
        )

    def test_experience_boundaries_and_invalid_numbers(self):
        rules = self.configure()
        for value in ("-1", "61", "NaN", "Infinity", "bad", "1.001"):
            self.assertFalse(
                CandidateEligibilityForm(
                    self.good(years_experience=value), job=self.job, rules=rules
                ).is_valid()
            )
        for value in ("1", "5"):
            self.assertEqual(
                evaluate_eligibility(
                    self.job, rules, self.good(years_experience=value)
                )["outcome"],
                "met",
            )
        self.job.min_experience, self.job.max_experience = Decimal(0), None
        self.assertEqual(
            evaluate_eligibility(self.job, rules, self.good(years_experience="0"))[
                "outcome"
            ],
            "met",
        )

    def test_nonblocking_gaps_require_review(self):
        rules = self.configure(False)
        for data, expected in [
            ({}, "incomplete"),
            (self.good(years_experience="0"), "review"),
        ]:
            result = evaluate_eligibility(self.job, rules, data)
            self.assertTrue(result["can_continue"])
            self.assertEqual(result["outcome"], expected)

    def test_location_alias_relocation_and_remote_restrictions(self):
        rules = self.configure()
        self.assertEqual(
            evaluate_eligibility(self.job, rules, self.good())["outcome"], "met"
        )
        self.assertEqual(
            evaluate_eligibility(
                self.job, rules, self.good(work_location="Delhi", relocate="yes")
            )["outcome"],
            "met",
        )
        self.job.work_mode = "remote"
        self.assertEqual(
            evaluate_eligibility(self.job, rules, self.good(work_location="Delhi"))[
                "outcome"
            ],
            "blocked",
        )

    def test_check_correct_rerun_and_stage_bypass(self):
        self.configure()
        self.login_seeker()
        start = reverse("jobs:application_start", args=[self.job.pk])
        self.assertRedirects(
            self.client.get(start + "?step=review"), start + "?step=eligibility"
        )
        self.assertEqual(
            self.flow("eligibility", {"action": "check"}).context["report"]["outcome"],
            "blocked",
        )
        self.assertEqual(
            self.flow(
                "eligibility", {"action": "continue", **self.good(skills="Python")}
            ).status_code,
            400,
        )
        self.assertEqual(ApplicationDraft.objects.get().stage, 1)
        self.assertEqual(
            self.flow("eligibility", {"action": "continue", **self.good()}).status_code,
            302,
        )
        self.assertEqual(ApplicationDraft.objects.get().stage, 2)

    def test_question_create_edit_delete_keeps_historical_answers(self):
        self.login_employer()
        url = reverse("jobs:screening_questions", args=[self.job.pk])
        self.assertEqual(self.client.post(url, self.qdata()).status_code, 302)
        q = ScreeningQuestion.objects.get()
        self.assertEqual(q.options, ["Git", "Docker", "Linux"])
        self.job.refresh_from_db()
        self.assertEqual(
            self.client.post(
                url, self.qdata(q, **{"questions-0-position": 5})
            ).status_code,
            302,
        )
        q.refresh_from_db()
        self.assertEqual(q.position, 5)
        app = Application.objects.create(job=self.job, job_seeker=self.seeker)
        answer = ScreeningAnswer.objects.create(
            application=app,
            question=q,
            question_snapshot={"prompt": "Original"},
            answer=["Git"],
            result="met",
        )
        self.job.refresh_from_db()
        self.assertEqual(
            self.client.post(
                url, self.qdata(q, **{"questions-0-DELETE": "on"})
            ).status_code,
            302,
        )
        answer.refresh_from_db()
        self.assertIsNone(answer.question_id)
        self.assertEqual(answer.question_snapshot["prompt"], "Original")

    def test_question_configuration_validation(self):
        base = {
            "prompt": "A question",
            "kind": "single",
            "options": "One\nTwo",
            "position": 1,
            "required": "on",
            "match_mode": "any",
            "expected_answers": "One",
            "is_blocking": "on",
        }
        self.assertTrue(ScreeningQuestionForm(base).is_valid())
        for change in [
            {"options": "One"},
            {"options": "One\none"},
            {"expected_answers": "Three"},
            {"required": ""},
            {"kind": "text", "options": ""},
            {"match_mode": "all"},
            {"match_mode": "none"},
            {"options": "\n".join(str(i) for i in range(21))},
        ]:
            self.assertFalse(
                ScreeningQuestionForm({**base, **change}).is_valid(), change
            )

    def test_reordering_saved_and_foreign_question_rejected(self):
        q1, q2 = (
            self.question(position=1),
            self.question(
                prompt="Second",
                position=2,
                kind="text",
                required=False,
                match_mode="none",
                expected_answers=[],
                is_blocking=False,
            ),
        )
        self.login_employer()
        url = reverse("jobs:screening_questions", args=[self.job.pk])
        data = self.qdata(
            q1,
            **{
                "questions-TOTAL_FORMS": 2,
                "questions-INITIAL_FORMS": 2,
                "questions-0-position": 2,
            },
        )
        data.update(
            {
                "questions-1-id": q2.pk,
                "questions-1-prompt": "Second",
                "questions-1-kind": "text",
                "questions-1-position": 1,
                "questions-1-match_mode": "none",
            }
        )
        self.assertEqual(self.client.post(url, data).status_code, 302)
        self.assertEqual(
            list(self.job.screening_questions.values_list("pk", flat=True)),
            [q2.pk, q1.pk],
        )
        other = Job.objects.create(
            title="Other",
            employer=self.other_employer,
            description="Other",
            requirements="Other",
            location="Delhi",
            job_type="full_time",
        )
        foreign = self.question(job=other, prompt="Foreign")
        self.job.refresh_from_db()
        data.update(
            {"revision": self.job.screening_revision, "questions-0-id": foreign.pk}
        )
        self.assertTrue(
            self.client.post(url, data).context["formset"].non_form_errors()
        )
        foreign.refresh_from_db()
        self.assertEqual(foreign.prompt, "Foreign")

    def test_question_formset_limits_stale_and_missing_management(self):
        self.login_employer()
        url = reverse("jobs:screening_questions", args=[self.job.pk])
        self.assertTrue(self.client.post(url, {}).context["formset"].non_form_errors())
        self.assertTrue(
            self.client.post(url, self.qdata(revision=99)).context["revision_error"]
        )
        r = self.client.post(url, self.qdata(**{"questions-TOTAL_FORMS": 10000}))
        self.assertTrue(r.context["formset"].non_form_errors())
        self.assertLessEqual(len(r.context["formset"].forms), 40)
        self.assertFalse(ScreeningQuestion.objects.exists())

    def test_all_question_types_server_validation(self):
        yes = self.question()
        single = self.question(
            prompt="When?",
            kind="single",
            options=["Now", "Later"],
            expected_answers=["Now"],
            position=2,
            is_blocking=False,
        )
        multiple = self.question(
            prompt="Tools?",
            kind="multiple",
            options=["Git", "Docker", "Linux"],
            expected_answers=["Git", "Linux"],
            match_mode="all",
            position=3,
            is_blocking=False,
        )
        text = self.question(
            prompt="Project?",
            kind="text",
            match_mode="none",
            expected_answers=[],
            is_blocking=False,
            position=4,
        )
        questions = list(self.job.screening_questions.all())
        data = {
            f"question_{yes.pk}": "yes",
            f"question_{single.pk}": "Now",
            f"question_{multiple.pk}": ["Git", "Linux"],
            f"question_{text.pk}": "My project",
        }
        form = CandidateScreeningForm(data, questions=questions)
        self.assertTrue(form.is_valid())
        self.assertEqual(
            [
                r["state"]
                for r in evaluate_questions(questions, form.cleaned_data)["rows"]
            ],
            ["met", "met", "met", "manual"],
        )
        for change in [
            {f"question_{yes.pk}": "true"},
            {f"question_{single.pk}": "Invalid"},
            {f"question_{multiple.pk}": ["Invalid"]},
            {f"question_{text.pk}": "x" * 2001},
        ]:
            self.assertFalse(
                CandidateScreeningForm(
                    {**data, **change}, questions=questions
                ).is_valid()
            )

    def test_required_no_and_optional_blank_are_distinct(self):
        q = self.question(expected_answers=["no"])
        form = CandidateScreeningForm({f"question_{q.pk}": "no"}, questions=[q])
        self.assertTrue(form.is_valid())
        self.assertEqual(evaluate_questions([q], form.cleaned_data)["outcome"], "met")
        q.required, q.is_blocking = False, False
        self.assertTrue(CandidateScreeningForm({}, questions=[q]).is_valid())
        self.assertEqual(evaluate_questions([q], {})["outcome"], "incomplete")

    def test_blocking_question_correction(self):
        q = self.question()
        self.login_seeker()
        self.flow("eligibility", {"action": "continue"})
        self.assertEqual(self.flow("questions").status_code, 400)
        self.assertEqual(
            self.flow("questions", {f"question_{q.pk}": "no"}).status_code, 400
        )
        self.assertEqual(ApplicationDraft.objects.get().stage, 2)
        self.assertEqual(
            self.flow("questions", {f"question_{q.pk}": "yes"}).status_code, 302
        )

    def test_full_submission_persists_evidence_resume_and_notification(self):
        self.configure()
        q = self.question()
        self.login_seeker()
        r = self.submit_application(
            {"resume": pdf_upload(), "cover_letter": "My project"},
            candidate=self.good(),
            answers={f"question_{q.pk}": "yes"},
            follow=True,
        )
        app = Application.objects.get()
        self.assertEqual((app.screening_outcome, app.status), ("met", "pending"))
        self.assertEqual(app.candidate_snapshot["years_experience"], "2.5")
        self.assertEqual(app.screening_answers.get().answer, "yes")
        self.assertTrue(app.resume_available)
        self.assertFalse(ApplicationDraft.objects.exists())
        self.assertEqual(Notification.objects.count(), 1)
        self.assertContains(r, "Submitted screening answers")

    def test_nonblocking_incomplete_submission_not_approved(self):
        self.configure(False)
        self.login_seeker()
        self.submit_application({"resume": pdf_upload()})
        app = Application.objects.get()
        self.assertEqual((app.screening_outcome, app.status), ("incomplete", "pending"))

    def test_direct_post_and_forged_result_cannot_bypass_review(self):
        self.login_seeker()
        r = self.client.post(
            reverse("jobs:apply_job", args=[self.job.pk]),
            {
                "eligibility": "met",
                "screening_outcome": "met",
                "status": "accepted",
                "resume": pdf_upload(),
            },
        )
        self.assertEqual(r.status_code, 400)
        self.assertFalse(Application.objects.exists())

    def test_consent_and_valid_review_token_required(self):
        self.login_seeker()
        review = self.prepare_application({"resume": pdf_upload()})
        self.assertEqual(self.final(review, consent="").status_code, 400)
        self.assertEqual(self.final(review, review_token="forged").status_code, 400)
        self.assertFalse(Application.objects.exists())

    def test_job_rule_change_requires_new_review(self):
        self.configure()
        self.login_seeker()
        review = self.prepare_application(
            {"resume": pdf_upload()}, candidate=self.good()
        )
        self.job.mandatory_skills += ", Kubernetes"
        self.job.save()
        self.assertEqual(self.final(review).status_code, 400)
        r = self.client.get(
            reverse("jobs:application_start", args=[self.job.pk]) + "?step=review"
        )
        self.assertEqual(r.context["step"], "eligibility")
        self.assertContains(r, "employer updated")
        self.assertFalse(Application.objects.exists())

    def test_new_question_invalidates_existing_review(self):
        self.login_seeker()
        review = self.prepare_application({"resume": pdf_upload()})
        self.question()
        self.assertEqual(self.final(review).status_code, 400)
        self.assertFalse(Application.objects.exists())

    def test_backend_revalidates_saved_data_not_client_results(self):
        self.configure()
        q = self.question()
        self.login_seeker()
        review = self.prepare_application(
            {"resume": pdf_upload()},
            candidate=self.good(),
            answers={f"question_{q.pk}": "yes"},
        )
        draft = ApplicationDraft.objects.get()
        draft.candidate_data["skills"] = "Python"
        draft.save()
        self.assertEqual(self.final(review).status_code, 400)
        draft.candidate_data, draft.answers_data = (
            self.good(),
            {f"question_{q.pk}": "invalid"},
        )
        draft.save()
        self.assertEqual(self.final(review).status_code, 400)
        self.assertFalse(Application.objects.exists())

    def test_review_token_bound_to_user_job_and_version(self):
        self.login_seeker()
        review = self.prepare_application({"resume": pdf_upload()})
        payload = signing.loads(
            review.context["final_form"].initial["review_token"], salt=TOKEN_SALT
        )
        for name, value in [
            ("candidate", self.other_seeker.pk),
            ("job", 9999),
            ("version", 999),
        ]:
            token = signing.dumps({**payload, name: value}, salt=TOKEN_SALT)
            self.assertEqual(self.final(review, review_token=token).status_code, 400)
        self.assertFalse(Application.objects.exists())

    def test_review_expiry_and_stale_tab(self):
        self.login_seeker()
        review = self.prepare_application({"resume": pdf_upload()})
        payload = signing.loads(
            review.context["final_form"].initial["review_token"], salt=TOKEN_SALT
        )
        with patch(
            "django.core.signing.TimestampSigner.timestamp",
            return_value=signing.b62_encode(int(timezone.now().timestamp()) - 7200),
        ):
            token = signing.dumps(payload, salt=TOKEN_SALT)
        self.assertEqual(self.final(review, review_token=token).status_code, 400)
        r = self.client.post(
            reverse("jobs:application_start", args=[self.job.pk]),
            {"step": "eligibility", "action": "continue", "draft_version": 0},
        )
        self.assertEqual(r.status_code, 409)
        self.assertEqual(ApplicationDraft.objects.get().stage, 4)

    def test_closed_paused_expired_jobs_block_final(self):
        self.login_seeker()
        review = self.prepare_application({"resume": pdf_upload()})
        for state in ("paused", "closed", "draft"):
            self.job.publication_status = state
            self.job.save()
            self.assertEqual(self.final(review).status_code, 404)
        self.job.publication_status, self.job.deadline = (
            "published",
            timezone.localdate() - timedelta(days=1),
        )
        self.job.save()
        self.assertEqual(self.final(review).status_code, 404)
        self.assertFalse(Application.objects.exists())

    def test_missing_resume_does_not_create_application(self):
        self.login_seeker()
        review = self.prepare_application({"resume": pdf_upload()})
        field = ApplicationDraft.objects.get().resume
        field.storage.delete(field.name)
        self.assertContains(
            self.final(review), "resume is missing or invalid", status_code=400
        )
        self.assertFalse(Application.objects.exists())

    def test_resume_source_is_explicit_and_profile_is_copied(self):
        self.login_seeker()
        self.flow("eligibility", {"action": "continue"})
        self.flow("questions")
        self.assertEqual(
            self.flow("resume", {"resume_source": "profile"}).status_code, 400
        )
        self.seeker.resume.save("profile.pdf", pdf_upload())
        self.assertEqual(
            self.flow(
                "resume", {"resume_source": "profile", "resume": pdf_upload()}
            ).status_code,
            400,
        )
        self.assertEqual(
            self.flow("resume", {"resume_source": "profile"}).status_code, 302
        )
        draft = ApplicationDraft.objects.get()
        self.assertNotEqual(draft.resume.name, self.seeker.resume.name)
        self.seeker.resume.delete()
        self.assertTrue(draft.resume_available)

    def test_private_draft_download_discard_and_csrf(self):
        self.login_seeker()
        self.prepare_application({"resume": pdf_upload()})
        resume, discard = (
            reverse("jobs:draft_resume", args=[self.job.pk]),
            reverse("jobs:discard_draft", args=[self.job.pk]),
        )
        self.assertEqual(self.client.get(resume).status_code, 200)
        self.assertEqual(self.client.get(discard).status_code, 405)
        strict = Client(enforce_csrf_checks=True)
        strict.force_login(self.seeker_user)
        self.assertEqual(strict.post(discard).status_code, 403)
        self.client.force_login(self.other_seeker_user)
        self.assertEqual(self.client.get(resume).status_code, 404)
        self.assertEqual(self.client.post(discard).status_code, 404)
        self.login_employer()
        self.assertEqual(self.client.get(resume).status_code, 403)
        self.login_seeker()
        field = ApplicationDraft.objects.get().resume
        with self.captureOnCommitCallbacks(execute=True):
            self.client.post(discard)
        self.assertFalse(ApplicationDraft.objects.exists())
        self.assertFalse(field.storage.exists(field.name))

    def test_cover_letter_edits_cannot_change_screening(self):
        self.configure()
        q = self.question()
        self.login_seeker()
        self.submit_application(
            {"resume": pdf_upload()},
            candidate=self.good(),
            answers={f"question_{q.pk}": "yes"},
        )
        app = Application.objects.get()
        before = app.eligibility_snapshot
        self.client.post(
            reverse("dashboard:edit_application", args=[app.pk]),
            {
                "cover_letter": "Updated",
                "candidate_snapshot": "{}",
                "eligibility_snapshot": "{}",
                f"question_{q.pk}": "no",
            },
        )
        app.refresh_from_db()
        self.assertEqual(app.cover_letter, "Updated")
        self.assertEqual(app.eligibility_snapshot, before)
        self.assertEqual(app.screening_answers.get().answer, "yes")

    def test_recruiter_edits_do_not_rewrite_submitted_evidence(self):
        q = self.question()
        self.login_seeker()
        self.submit_application(
            {"resume": pdf_upload()}, answers={f"question_{q.pk}": "yes"}
        )
        app = Application.objects.get()
        before = app.job_snapshot
        self.job.description, q.prompt = "New description", "New question"
        self.job.save()
        q.save()
        app.refresh_from_db()
        self.assertEqual(app.job_snapshot, before)
        self.login_employer()
        r = self.client.get(reverse("dashboard:candidate_detail", args=[app.pk]))
        self.assertContains(r, "Can you attend agreed team sessions?")
        self.assertNotContains(r, "New question")

    def test_receipts_and_screening_filters_are_owner_scoped(self):
        self.login_seeker()
        self.submit_application({"resume": pdf_upload()})
        app = Application.objects.get()
        receipt = reverse("dashboard:application_detail", args=[app.pk])
        self.assertEqual(self.client.get(receipt)["Cache-Control"], "private, no-store")
        self.client.force_login(self.other_seeker_user)
        self.assertEqual(self.client.get(receipt).status_code, 404)
        self.login_employer()
        self.assertEqual(self.client.get(receipt).status_code, 403)
        self.assertEqual(
            self.client.get(
                reverse("dashboard:employer_applications"), {"screening": "no_rules"}
            )
            .context["page_obj"]
            .paginator.count,
            1,
        )
        self.client.force_login(self.other_employer_user)
        self.assertEqual(
            self.client.get(
                reverse("dashboard:candidate_detail", args=[app.pk])
            ).status_code,
            404,
        )

    def test_duplicate_withdrawn_application_cannot_resubmit(self):
        self.login_seeker()
        review = self.prepare_application({"resume": pdf_upload()})
        self.final(review)
        self.final(review)
        app = Application.objects.get()
        self.assertEqual(Notification.objects.count(), 1)
        self.client.post(reverse("dashboard:withdraw_application", args=[app.pk]))
        self.final(review)
        self.assertEqual(Application.objects.count(), 1)
        app.refresh_from_db()
        self.assertEqual(app.status, "withdrawn")

    def test_database_constraints_and_foreign_question_answer(self):
        with self.assertRaises(IntegrityError), transaction.atomic():
            Job.objects.filter(pk=self.job.pk).update(
                min_experience=10, max_experience=2
            )
        with self.assertRaises(IntegrityError), transaction.atomic():
            ApplicationDraft.objects.create(
                job=self.job, job_seeker=self.seeker, stage=6
            )
        app = Application.objects.create(job=self.job, job_seeker=self.seeker)
        q = self.question()
        ScreeningAnswer.objects.create(application=app, question=q, result="met")
        with self.assertRaises(IntegrityError), transaction.atomic():
            ScreeningAnswer.objects.create(application=app, question=q, result="met")
        other = Job.objects.create(
            title="Other",
            employer=self.other_employer,
            description="Other",
            requirements="Other",
            location="Delhi",
            job_type="full_time",
        )
        q = self.question(job=other)
        with self.assertRaises(ValidationError):
            ScreeningAnswer(application=app, question=q, result="manual").clean()

    def test_retention_is_dry_run_by_default(self):
        old = ApplicationDraft.objects.create(job=self.job, job_seeker=self.seeker)
        recent = ApplicationDraft.objects.create(
            job=self.job, job_seeker=self.other_seeker
        )
        ApplicationDraft.objects.filter(pk=old.pk).update(
            updated_at=timezone.now() - timedelta(days=31)
        )
        output = StringIO()
        call_command("cleanup_application_drafts", stdout=output)
        self.assertIn("Dry run: 1", output.getvalue())
        self.assertEqual(ApplicationDraft.objects.count(), 2)
        call_command("cleanup_application_drafts", apply=True, stdout=StringIO())
        self.assertFalse(ApplicationDraft.objects.filter(pk=old.pk).exists())
        self.assertTrue(ApplicationDraft.objects.filter(pk=recent.pk).exists())

    def test_html_escaping_and_config_fingerprint(self):
        q = self.question(
            prompt="<script>alert(1)</script>",
            kind="text",
            match_mode="none",
            expected_answers=[],
            is_blocking=False,
        )
        self.login_seeker()
        self.submit_application(
            {"resume": pdf_upload()},
            answers={f"question_{q.pk}": "<script>alert(2)</script>"},
        )
        app = Application.objects.get()
        r = self.client.get(reverse("dashboard:application_detail", args=[app.pk]))
        self.assertNotContains(r, "<script>alert")
        self.assertContains(r, "&lt;script&gt;")
        first = fingerprint(job_snapshot(self.job, [], [q]))
        q.prompt = "Changed"
        self.assertNotEqual(first, fingerprint(job_snapshot(self.job, [], [q])))
