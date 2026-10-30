"""Integration coverage for database-backed local practice listings."""

from datetime import timedelta
from io import StringIO
from unittest.mock import patch
from django.core.management import call_command
from django.core.management.base import CommandError
from django.test import Client, override_settings
from django.urls import reverse
from django.utils import timezone
from core.test_support import PortalTestCase, pdf_upload
from apps.accounts.models import CustomUser, Employer
from .demo_catalog import JOBS, DEMO_PREFIX
from .models import (
    Job,
    Category,
    Application,
    ApplicationDraft,
    SavedJob,
    ScreeningQuestion,
    EligibilityRule,
)
from .locations import location_query
from .screening import evaluate_eligibility


@override_settings(DEBUG=True)
class DemoJobTests(PortalTestCase):
    def seed(self, **options):
        with patch(
            "apps.accounts.management.commands.backup_database.Command.handle",
            return_value=None,
        ) as backup:
            out = StringIO()
            call_command("seed_demo_jobs", stdout=out, **options)
            backup.assert_called_once()
        return out.getvalue()

    def demos(self):
        return Job.objects.filter(
            is_demo=True, demo_key__startswith=DEMO_PREFIX
        ).select_related("employer__user", "category")

    def candidate(self, job):
        return dict(
            qualification=job.eligibility_rules.get(kind="qualification").values[0],
            years_experience=str(job.min_experience),
            skills=job.mandatory_skills,
            work_location=job.location,
            relocate="yes",
            work_arrangement="yes",
        )

    def answers(self, job):
        return {
            f"question_{q.pk}": "yes"
            if q.kind == "yes_no"
            else q.options[0]
            if q.kind == "single"
            else q.expected_answers
            if q.kind == "multiple"
            else "I would define test cases, implement a small solution and explain the result."
            for q in job.screening_questions.all()
        }

    def search_ids(self, **params):
        response = self.client.get("/jobs/", params)
        self.assertEqual(response.status_code, 200)
        self.assertFalse(response.context["form"].errors)
        return set(
            response.context["page_obj"].paginator.object_list.values_list(
                "pk", flat=True
            )
        )

    def test_complete_catalog_and_typed_questions(self):
        self.assertIn("Created 18", self.seed())
        self.assertEqual(self.demos().count(), 18)
        self.assertEqual(
            self.demos().order_by().values("category_id").distinct().count(), 15
        )
        self.assertEqual(Employer.objects.filter(is_demo=True).count(), 4)
        self.assertFalse(
            any(
                e.user.has_usable_password()
                for e in Employer.objects.filter(is_demo=True)
            )
        )
        self.assertEqual(
            len(set(self.demos().values_list("description", flat=True))), 18
        )
        for job in self.demos():
            job.full_clean()
            self.assertTrue(job.is_open and job.accepts_demo_applications)
            self.assertNotIn("DEVELOPMENT SAMPLE", job.card_description)
            for field in [
                "description",
                "responsibilities",
                "qualifications",
                "requirements",
                "mandatory_skills",
                "preferred_skills",
                "benefits",
                "application_instructions",
            ]:
                self.assertTrue(getattr(job, field), (job.title, field))
            self.assertEqual(job.deadline, timezone.localdate() + timedelta(days=60))
            self.assertEqual(job.screening_questions.count(), 4)
            self.assertEqual(
                set(job.screening_questions.values_list("kind", flat=True)),
                {"yes_no", "single", "multiple", "text"},
            )
            for q in job.screening_questions.all():
                q.full_clean()
                self.assertTrue(q.required)
        self.assertFalse(Application.objects.exists())

    def test_idempotence_preserves_edits_users_and_rules(self):
        users = list(CustomUser.objects.values())
        original = Job.objects.values().get(pk=self.job.pk)
        self.seed()
        job = self.demos().first()
        job.description = "Recruiter edit"
        job.is_active = False
        job.publication_status = "paused"
        job.save()
        q = job.screening_questions.first()
        q.prompt = "Recruiter question edit"
        q.save()
        user = job.employer.user
        user.set_password("Fixture-only-Private-28!")
        user.save()

        def snap():
            return (
                list(Job.objects.order_by("pk").values()),
                list(ScreeningQuestion.objects.order_by("pk").values()),
                list(EligibilityRule.objects.order_by("pk").values()),
                CustomUser.objects.get(pk=user.pk).password,
            )

        before = snap()
        self.assertIn("Created 0", self.seed())
        self.assertEqual(before, snap())
        self.assertEqual(Job.objects.values().get(pk=self.job.pk), original)
        self.assertEqual(
            list(CustomUser.objects.filter(pk__in=[u["id"] for u in users]).values()),
            users,
        )

    def test_production_hiding_and_command_guard(self):
        self.seed()
        job = self.demos().first()
        self.login_seeker()
        with override_settings(DEBUG=False):
            with self.assertRaises(CommandError):
                call_command("seed_demo_jobs", stdout=StringIO())
            self.assertFalse(job.accepts_demo_applications)
            self.assertNotIn(job.pk, self.search_ids())
            for url in [
                job.get_absolute_url(),
                reverse("jobs:application_start", args=[job.pk]),
            ]:
                self.assertEqual(self.client.get(url).status_code, 404)
            self.assertEqual(
                self.client.post(
                    reverse("jobs:apply_job", args=[job.pk]), {}
                ).status_code,
                404,
            )
        self.assertFalse(Application.objects.exists())

    def test_reserved_username_collision(self):
        user = CustomUser.objects.create_user(
            "joblyfy_demo_stack", password="Existing-fixture-728!"
        )
        saved = user.password
        with self.assertRaises(CommandError):
            self.seed()
        self.assertFalse(self.demos().exists())
        self.assertFalse(Employer.objects.filter(is_demo=True).exists())
        user.refresh_from_db()
        self.assertEqual(user.password, saved)

    def test_reserved_job_identifier_collision(self):
        self.job.demo_key = DEMO_PREFIX + JOBS[0]["slug"]
        self.job.save()
        with self.assertRaises(CommandError):
            self.seed()
        self.assertFalse(self.demos().exists())
        self.assertFalse(Employer.objects.filter(is_demo=True).exists())
        self.job.refresh_from_db()
        self.assertFalse(self.job.is_demo)

    def test_backup_failure_stops_mutation(self):
        with patch(
            "apps.accounts.management.commands.backup_database.Command.handle",
            side_effect=CommandError("Backup failed"),
        ):
            with self.assertRaises(CommandError):
                call_command("seed_demo_jobs", stdout=StringIO())
        self.assertFalse(self.demos().exists())

    def test_lifecycle_keeps_history_and_real_jobs(self):
        self.seed()
        job = self.demos().first()
        app = Application.objects.create(job=job, job_seeker=self.seeker)
        self.seed(deactivate=True)
        self.assertEqual(self.demos().open().count(), 0)
        self.seed()
        self.assertEqual(self.demos().open().count(), 0)
        self.seed(refresh_deadlines=True)
        self.assertEqual(self.demos().open().count(), 0)
        self.seed(reactivate=True)
        self.assertEqual(self.demos().open().count(), 18)
        app.refresh_from_db()
        self.assertEqual(app.job_id, job.pk)
        self.job.refresh_from_db()
        self.assertTrue(self.job.is_active)

    def test_remove_unused_protects_referenced_records(self):
        self.seed()
        jobs = list(self.demos()[:3])
        Application.objects.create(job=jobs[0], job_seeker=self.seeker)
        ApplicationDraft.objects.create(job=jobs[1], job_seeker=self.seeker)
        SavedJob.objects.create(job=jobs[2], job_seeker=self.seeker)
        counts = (CustomUser.objects.count(), Category.objects.count())
        self.assertIn("retained 3", self.seed(remove_unused=True))
        self.assertEqual(
            set(self.demos().values_list("pk", flat=True)), {j.pk for j in jobs}
        )
        self.assertEqual((CustomUser.objects.count(), Category.objects.count()), counts)
        self.seed()
        self.assertEqual(self.demos().count(), 18)
        self.assertEqual(Application.objects.get().job_id, jobs[0].pk)

    def test_all_categories_and_locations(self):
        self.seed()
        ids = set(self.demos().values_list("pk", flat=True))
        for category in Category.objects.filter(
            pk__in=self.demos().values("category_id")
        ):
            self.assertEqual(
                self.search_ids(category=category.pk),
                set(
                    self.demos().filter(category=category).values_list("pk", flat=True)
                ),
            )
            self.assertEqual(
                self.client.get(
                    reverse("jobs:category_detail", args=[category.pk])
                ).status_code,
                200,
            )
        for place in [
            "Mohali",
            "SAS Nagar",
            "Punjab",
            "Chandigarh",
            "Ludhiana",
            "Delhi NCR",
            "Delhi",
            "Bengaluru",
            "Bangalore",
            "Hyderabad",
            "Pune",
            "Remote",
            "Work from home",
        ]:
            expected = set(
                self.demos().filter(location_query(place)).values_list("pk", flat=True)
            )
            self.assertTrue(expected, place)
            self.assertEqual(self.search_ids(location=place) & ids, expected, place)

    def test_title_skills_companies_combined_filters(self):
        self.seed()
        for job in self.demos():
            for query in [
                job.title,
                job.mandatory_skill_list[0],
                job.employer.company_name.split()[0],
            ]:
                self.assertIn(job.pk, self.search_ids(search=query))
            self.assertIn(
                job.pk,
                self.search_ids(
                    search=job.mandatory_skill_list[0],
                    category=job.category_id,
                    location=job.location,
                    work_mode=job.work_mode,
                    job_type=job.job_type,
                    experience=job.experience_level,
                    company=job.employer_id,
                    min_salary=int(job.salary_min),
                    max_salary=int(job.salary_max),
                    posted="7",
                ),
            )
        self.assertFalse(self.search_ids(search="NoMatchingFixtureXYZ"))

    def test_filters_sorting_and_pagination(self):
        self.seed()
        for param, field in [
            ("job_type", "job_type"),
            ("experience", "experience_level"),
            ("work_mode", "work_mode"),
        ]:
            for value in (
                self.demos().order_by().values_list(field, flat=True).distinct()
            ):
                self.assertEqual(
                    self.search_ids(**{param: value}),
                    set(
                        Job.objects.open()
                        .filter(**{field: value})
                        .values_list("pk", flat=True)
                    ),
                )
        self.assertEqual(
            self.search_ids(min_salary=800000, max_salary=1000000),
            set(
                Job.objects.open()
                .filter(salary_max__gte=800000, salary_min__lte=1000000)
                .values_list("pk", flat=True)
            ),
        )
        r = self.client.get("/jobs/", {"sort": "oldest"})
        jobs = list(r.context["page_obj"].paginator.object_list)
        self.assertEqual(
            [j.pk for j in jobs],
            [j.pk for j in sorted(jobs, key=lambda j: (j.posted_date, j.pk))],
        )
        seen = []
        for page in range(1, 4):
            seen.extend(
                j.pk for j in self.client.get("/jobs/", {"page": page}).context["jobs"]
            )
        self.assertEqual(len(seen), 19)
        self.assertEqual(len(set(seen)), 19)

    def test_suggestions_home_and_all_details(self):
        self.seed()
        for place in [
            "Mohali",
            "Chandigarh",
            "Ludhiana",
            "Delhi NCR",
            "Bengaluru",
            "Hyderabad",
            "Pune",
            "Remote",
        ]:
            rows = self.client.get("/locations/suggest/", {"q": place}).json()[
                "results"
            ]
            self.assertTrue(rows)
            for row in rows:
                self.assertEqual(
                    row["count"],
                    Job.objects.open().filter(location_query(row["value"])).count(),
                )
        r = self.client.get("/")
        self.assertEqual(r.context["listing_count"], 19)
        self.assertEqual(r.context["sample_job_count"], 18)
        self.assertEqual(r.context["job_count"], 1)
        self.assertEqual(len(r.context["featured_jobs"]), 3)
        self.assertEqual(len(r.context["recent_jobs"]), 6)
        self.assertContains(r, "18 samples")
        for job in self.demos():
            self.assertContains(
                self.client.get(job.get_absolute_url()),
                job.responsibilities.splitlines()[0],
            )

    def test_saved_eligibility_rules_and_preferred_skills(self):
        self.seed()
        for job in self.demos():
            rules = list(job.eligibility_rules.all())
            candidate = self.candidate(job)
            self.assertTrue(evaluate_eligibility(job, rules, candidate)["can_continue"])
            self.assertFalse(
                evaluate_eligibility(
                    job,
                    rules,
                    {**candidate, "skills": ", ".join(job.mandatory_skill_list[1:])},
                )["can_continue"]
            )
            unknown = evaluate_eligibility(job, rules, {})
            self.assertFalse(unknown["can_continue"])
            self.assertTrue(all(r["state"] == "unknown" for r in unknown["rows"]))
            if job.work_mode == "remote":
                self.assertFalse(job.eligibility_rules.filter(kind="location").exists())

    def test_every_role_accepts_reviewed_practice_application(self):
        self.seed()
        self.login_seeker()
        for job in self.demos():
            response = self.submit_application(
                {"resume": pdf_upload()},
                job=job,
                candidate=self.candidate(job),
                answers=self.answers(job),
            )
            self.assertEqual(response.status_code, 302)
            app = Application.objects.get(job=job, job_seeker=self.seeker)
            self.assertEqual(app.screening_answers.count(), 4)
            self.assertEqual(app.screening_outcome, "met")
            self.assertTrue(app.job_snapshot["is_demo"])
            self.assertEqual(app.job_snapshot["demo_key"], job.demo_key)
            self.assertTrue(
                all(
                    a.question.job_id == job.pk
                    for a in app.screening_answers.select_related("question")
                )
            )
            self.assertContains(self.client.get(response.url), "Practice application")
        self.assertEqual(Application.objects.count(), 18)
        self.assertFalse(ApplicationDraft.objects.exists())
        for company in Employer.objects.filter(is_demo=True):
            self.client.force_login(company.user)
            r = self.client.get(reverse("dashboard:employer_dashboard"))
            self.assertEqual(r.context["total_jobs"], company.jobs.count())
            self.assertEqual(
                r.context["stats"]["total"],
                Application.objects.filter(job__employer=company).count(),
            )

    def test_csrf_closed_duplicates_and_permissions(self):
        self.seed()
        job = self.demos().first()
        self.login_seeker()
        review = self.prepare_application(
            {"resume": pdf_upload()},
            job=job,
            candidate=self.candidate(job),
            answers=self.answers(job),
        )
        url = reverse("jobs:apply_job", args=[job.pk])
        data = {
            "review_token": review.context["final_form"].initial["review_token"],
            "consent": "on",
        }
        csrf = Client(enforce_csrf_checks=True)
        csrf.force_login(self.seeker_user)
        self.assertEqual(csrf.post(url, data).status_code, 403)
        job.is_active = False
        job.publication_status = "closed"
        job.save()
        self.assertEqual(self.client.post(url, data).status_code, 404)
        job.is_active = True
        job.publication_status = "published"
        job.save()
        self.assertEqual(self.client.post(url, data).status_code, 302)
        self.client.post(url, data)
        self.assertEqual(Application.objects.count(), 1)
        app = Application.objects.get()
        self.client.force_login(job.employer.user)
        self.assertEqual(
            self.client.get(
                reverse("dashboard:candidate_detail", args=[app.pk])
            ).status_code,
            200,
        )
        self.client.force_login(self.other_employer_user)
        self.assertEqual(
            self.client.get(
                reverse("dashboard:candidate_detail", args=[app.pk])
            ).status_code,
            404,
        )
        self.client.force_login(self.other_seeker_user)
        self.assertEqual(
            self.client.get(
                reverse("dashboard:application_resume", args=[app.pk])
            ).status_code,
            404,
        )

    def test_stipends_and_no_fake_company_reviews(self):
        self.seed()
        for job in self.demos().filter(job_type="internship"):
            self.assertIn("/ month (sample stipend)", job.salary_display)
            self.assertContains(
                self.client.get(job.get_absolute_url()), "12 × this monthly band"
            )
        self.login_seeker()
        for company in Employer.objects.filter(is_demo=True):
            self.assertContains(
                self.client.get(company.get_absolute_url()), "Fictional sample company"
            )
            self.assertEqual(
                self.client.post(
                    reverse("jobs:company_review", args=[company.pk]),
                    {"rating": 5, "title": "Fixture", "body": "Fixture"},
                ).status_code,
                404,
            )

    def test_recruiter_manages_only_owned_catalog_jobs(self):
        self.seed()
        job = self.demos().first()
        self.client.force_login(job.employer.user)
        self.assertEqual(
            self.client.get(reverse("jobs:edit_job", args=[job.pk])).status_code, 200
        )
        self.assertEqual(
            self.client.get(
                reverse("jobs:screening_questions", args=[job.pk])
            ).status_code,
            200,
        )
        self.assertEqual(
            self.client.post(
                reverse("jobs:change_job_status", args=[job.pk]), {"status": "paused"}
            ).status_code,
            302,
        )
        job.refresh_from_db()
        self.assertEqual(job.publication_status, "paused")
        self.assertEqual(
            self.client.get(reverse("jobs:edit_job", args=[self.job.pk])).status_code,
            404,
        )
