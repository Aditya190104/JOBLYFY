from datetime import timedelta
from django.core.files.uploadedfile import SimpleUploadedFile
from django.db import IntegrityError, transaction
from django.test import Client
from django.urls import reverse
from django.utils import timezone
from core.test_support import PortalTestCase, pdf_upload
from .models import Job, Application, SavedJob


class JobTests(PortalTestCase):
    def job_data(self, **overrides):
        return {
            "title": "Frontend Engineer",
            "description": "Build accessible interfaces",
            "requirements": "HTML CSS React",
            "location": "Ludhiana",
            "salary": "₹4–6 LPA",
            "job_type": "full_time",
            "category": self.category.pk,
            "experience_level": "entry",
            "work_mode": "remote",
            "deadline": (timezone.localdate() + timedelta(days=20)).isoformat(),
            "benefits": "Learning budget",
            **overrides,
        }

    def test_public_pages_and_database_counts(self):
        for name, args in [
            ("home", []),
            ("job_list", []),
            ("search_jobs", []),
            ("categories", []),
            ("category_detail", [self.category.pk]),
            ("companies", []),
            ("company_detail", [self.employer.pk]),
            ("job_detail", [self.job.pk]),
            ("about", []),
        ]:
            with self.subTest(name=name):
                self.assertEqual(
                    self.client.get(reverse("jobs:" + name, args=args)).status_code, 200
                )
        response = self.client.get(reverse("jobs:home"))
        self.assertEqual(response.context["job_count"], 1)
        self.assertEqual(response.context["company_count"], 2)
        self.assertEqual(response.context["category_count"], 1)

    def test_keyword_location_category_company_and_other_filters(self):
        filters = [
            {"search": "python"},
            {"search": "Test Company"},
            {"location": "Moh"},
            {"category": self.category.pk},
            {"company": self.employer.pk},
            {"job_type": "full_time"},
            {"experience": "entry"},
            {"work_mode": "hybrid"},
            {
                "search": "Django",
                "location": "Mohali",
                "category": self.category.pk,
                "company": self.employer.pk,
                "work_mode": "hybrid",
            },
        ]
        for params in filters:
            with self.subTest(params=params):
                r = self.client.get(reverse("jobs:job_list"), params)
                self.assertEqual(r.status_code, 200)
                self.assertEqual(r.context["page_obj"].paginator.count, 1)
        for params in [
            {"search": "unmatched"},
            {"company": self.other_employer.pk},
            {"work_mode": "remote"},
        ]:
            self.assertEqual(
                self.client.get(reverse("jobs:job_list"), params)
                .context["page_obj"]
                .paginator.count,
                0,
            )

    def test_invalid_filters_are_explained_not_ignored(self):
        r = self.client.get(
            reverse("jobs:job_list"),
            {"category": "bad", "sort": "sql;drop", "experience": "expert"},
        )
        self.assertEqual(r.status_code, 200)
        self.assertTrue(r.context["form"].errors)
        self.assertEqual(r.context["page_obj"].paginator.count, 0)
        self.assertContains(r, "Select a valid choice")

    def test_pagination_sorting_and_encoded_query_parameters(self):
        for n in range(12):
            Job.objects.create(
                title=f"Python C++ {n:02}",
                employer=self.employer,
                category=self.category,
                description="Python",
                requirements="Python",
                location="Mohali",
                salary="₹5 LPA",
                job_type="full_time",
            )
        r = self.client.get(
            reverse("jobs:job_list"), {"search": "C++", "sort": "title", "page": 2}
        )
        self.assertEqual(r.context["page_obj"].number, 2)
        self.assertEqual(len(r.context["page_obj"]), 3)
        self.assertEqual(r.context["page_obj"][0].title, "Python C++ 09")
        self.assertContains(r, "search=C%2B%2B")
        self.assertEqual(
            self.client.get(reverse("jobs:job_list"), {"page": "oops"})
            .context["page_obj"]
            .number,
            1,
        )
        self.assertEqual(
            self.client.get(reverse("jobs:job_list"), {"page": 999})
            .context["page_obj"]
            .number,
            2,
        )

    def test_expired_inactive_and_disabled_employer_jobs_not_listed(self):
        self.job.deadline = timezone.localdate() - timedelta(days=1)
        self.job.save()
        r = self.client.get(reverse("jobs:job_list"))
        self.assertEqual(r.context["page_obj"].paginator.count, 0)
        self.assertContains(
            self.client.get(self.job.get_absolute_url()), "no longer accepting"
        )
        self.job.deadline = timezone.localdate()
        self.job.save()
        self.assertEqual(
            self.client.get(reverse("jobs:job_list"))
            .context["page_obj"]
            .paginator.count,
            1,
        )
        self.job.is_active = False
        self.job.save()
        self.assertEqual(self.client.get(self.job.get_absolute_url()).status_code, 404)
        self.job.is_active = True
        self.job.save()
        self.employer_user.is_active = False
        self.employer_user.save()
        self.assertEqual(
            self.client.get(reverse("jobs:job_list"))
            .context["page_obj"]
            .paginator.count,
            0,
        )

    def test_post_job_keeps_all_fields(self):
        self.login_employer()
        r = self.client.post(reverse("jobs:post_job"), self.job_data(), follow=True)
        self.assertEqual(r.status_code, 200)
        job = Job.objects.get(title="Frontend Engineer")
        self.assertEqual(job.employer, self.employer)
        self.assertEqual(job.requirements, "HTML CSS React")
        self.assertEqual(job.category, self.category)
        self.assertEqual(job.work_mode, "remote")
        self.assertEqual(job.benefits, "Learning budget")
        self.assertIsNotNone(job.deadline)

    def test_posting_validation_and_wrong_role(self):
        r = self.client.get(reverse("jobs:post_job"))
        self.assertEqual(r.status_code, 302)
        self.assertIn("/accounts/login/", r.url)
        self.login_seeker()
        self.assertEqual(
            self.client.post(reverse("jobs:post_job"), self.job_data()).status_code, 403
        )
        self.login_employer()
        r = self.client.post(
            reverse("jobs:post_job"),
            self.job_data(deadline="2020-01-01", requirements=""),
        )
        self.assertContains(r, "Choose today or a future date")
        self.assertContains(r, "This field is required.")
        self.assertEqual(Job.objects.count(), 1)

    def test_job_edit_and_toggle_owner_only(self):
        self.login_employer()
        self.assertEqual(
            self.client.post(
                reverse("jobs:edit_job", args=[self.job.pk]),
                self.job_data(title="Updated Job"),
            ).status_code,
            302,
        )
        self.job.refresh_from_db()
        self.assertEqual(self.job.title, "Updated Job")
        self.assertEqual(
            self.client.get(reverse("jobs:toggle_job", args=[self.job.pk])).status_code,
            405,
        )
        self.client.post(reverse("jobs:toggle_job", args=[self.job.pk]))
        self.job.refresh_from_db()
        self.assertFalse(self.job.is_active)
        self.assertEqual(self.client.get(self.job.get_absolute_url()).status_code, 200)
        self.client.force_login(self.other_employer_user)
        self.assertEqual(
            self.client.get(reverse("jobs:edit_job", args=[self.job.pk])).status_code,
            404,
        )
        self.assertEqual(
            self.client.post(
                reverse("jobs:toggle_job", args=[self.job.pk])
            ).status_code,
            404,
        )

    def test_expired_job_cannot_be_reactivated_without_new_deadline(self):
        self.login_employer()
        self.job.is_active = False
        self.job.deadline = timezone.localdate() - timedelta(days=1)
        self.job.save()
        self.client.post(reverse("jobs:toggle_job", args=[self.job.pk]))
        self.job.refresh_from_db()
        self.assertFalse(self.job.is_active)

    def test_application_submission_resume_snapshot_and_duplicate(self):
        self.login_seeker()
        r = self.submit_application({"cover_letter": "Hello team", "resume": pdf_upload()}, follow=True)
        self.assertEqual(r.status_code, 200)
        app = Application.objects.get()
        self.assertEqual(app.status, "pending")
        self.assertEqual(app.job_seeker, self.seeker)
        self.assertTrue(app.resume.storage.exists(app.resume.name))
        self.client.post(
            reverse("jobs:apply_job", args=[self.job.pk]), {"resume": pdf_upload()}
        )
        self.assertEqual(Application.objects.count(), 1)
        with self.assertRaises(IntegrityError), transaction.atomic():
            Application.objects.create(job=self.job, job_seeker=self.seeker)

    def test_application_uses_saved_resume_and_keeps_snapshot(self):
        self.seeker.resume.save("profile.pdf", pdf_upload())
        self.login_seeker()
        r = self.submit_application({"cover_letter": "From my profile"})
        self.assertEqual(r.status_code, 302)
        app = Application.objects.get()
        original = app.resume.read()
        app.resume.close()
        self.assertNotEqual(app.resume.name, self.seeker.resume.name)
        self.seeker.resume.delete()
        self.assertTrue(app.resume.storage.exists(app.resume.name))
        app.resume.open("rb")
        self.assertEqual(app.resume.read(), original)
        app.resume.close()

    def test_application_missing_resume_invalid_file_and_expired_job(self):
        self.login_seeker()
        url = reverse("jobs:apply_job", args=[self.job.pk])
        self.assertContains(self.client.post(url, {"cover_letter": "Hello"}), "Complete eligibility", status_code=400)
        from .models import ApplicationDraft
        flow = reverse("jobs:application_start", args=[self.job.pk])
        self.client.post(flow, {"step": "eligibility", "action": "continue", "draft_version": 0})
        draft = ApplicationDraft.objects.get()
        self.client.post(flow, {"step": "questions", "draft_version": draft.version})
        draft.refresh_from_db()
        self.assertContains(self.client.post(flow, {"step": "resume", "draft_version": draft.version, "resume_source": "upload"}), "Upload a resume", status_code=400)
        self.assertEqual(self.client.post(flow, {"step": "resume", "draft_version": draft.version, "resume_source": "upload", "resume": SimpleUploadedFile("resume.pdf", b"not a pdf")}).status_code, 400)
        self.assertEqual(Application.objects.count(), 0)
        self.job.deadline = timezone.localdate() - timedelta(days=1)
        self.job.save()
        self.assertEqual(
            self.client.post(url, {"resume": pdf_upload()}).status_code, 404
        )
        self.assertEqual(Application.objects.count(), 0)

    def test_apply_requires_post_correct_role_and_csrf(self):
        self.login_seeker()
        url = reverse("jobs:apply_job", args=[self.job.pk])
        self.assertEqual(self.client.get(url).status_code, 405)
        strict = Client(enforce_csrf_checks=True)
        strict.force_login(self.seeker_user)
        self.assertEqual(strict.post(url, {"resume": pdf_upload()}).status_code, 403)
        self.login_employer()
        self.assertEqual(
            self.client.post(url, {"resume": pdf_upload()}).status_code, 403
        )

    def test_save_unsave_and_cross_role_protection(self):
        self.login_seeker()
        url = reverse("jobs:save_job", args=[self.job.pk])
        self.assertEqual(self.client.get(url).status_code, 405)
        self.client.post(url)
        self.assertEqual(SavedJob.objects.count(), 1)
        self.assertContains(
            self.client.get(reverse("dashboard:saved_jobs")), "Django Developer"
        )
        self.client.post(url)
        self.assertEqual(SavedJob.objects.count(), 0)
        self.login_employer()
        self.assertEqual(self.client.post(url).status_code, 403)

    def test_company_directory_and_category_counts_exclude_closed_jobs(self):
        response = self.client.get(reverse("jobs:companies"), {"search": "Mohali"})
        self.assertEqual(response.context["page_obj"].paginator.count, 1)
        self.assertEqual(response.context["companies"][0].open_count, 1)
        self.job.is_active = False
        self.job.save()
        response = self.client.get(reverse("jobs:categories"))
        self.assertEqual(response.context["categories"][0].open_count, 0)

    def test_empty_states_and_query_efficiency(self):
        Job.objects.all().delete()
        for name in ["home", "job_list", "categories", "companies"]:
            self.assertEqual(self.client.get(reverse("jobs:" + name)).status_code, 200)
        self.assertContains(
            self.client.get(reverse("jobs:home")), "No jobs have been published yet"
        )
        self.assertContains(
            self.client.get(reverse("jobs:job_list")), "No matching opportunities"
        )

    def test_html_is_escaped_and_security_headers_present(self):
        self.job.title = "<script>alert(1)</script>"
        self.job.save()
        r = self.client.get(self.job.get_absolute_url())
        self.assertNotContains(r, "<script>alert(1)</script>")
        self.assertContains(r, "&lt;script&gt;")
        self.assertIn("object-src 'none'", r["Content-Security-Policy"])
        self.assertEqual(r["X-Content-Type-Options"], "nosniff")
