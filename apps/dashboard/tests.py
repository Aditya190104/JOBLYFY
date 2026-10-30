from django.urls import reverse
from core.test_support import PortalTestCase, pdf_upload
from apps.jobs.models import Job, Application


class DashboardTests(PortalTestCase):
    def application(self, status="pending", **kwargs):
        return Application.objects.create(
            job=self.job, job_seeker=self.seeker, status=status, **kwargs
        )

    def test_dashboard_redirects_and_role_boundaries(self):
        self.assertEqual(self.client.get(reverse("dashboard:home")).status_code, 302)
        self.login_seeker()
        self.assertRedirects(
            self.client.get(reverse("dashboard:home")),
            reverse("dashboard:jobseeker_dashboard"),
        )
        for name in ["employer_dashboard", "manage_jobs", "employer_applications"]:
            self.assertEqual(
                self.client.get(reverse("dashboard:" + name)).status_code, 403
            )
        self.login_employer()
        self.assertRedirects(
            self.client.get(reverse("dashboard:home")),
            reverse("dashboard:employer_dashboard"),
        )
        for name in ["jobseeker_dashboard", "saved_jobs"]:
            self.assertEqual(
                self.client.get(reverse("dashboard:" + name)).status_code, 403
            )

    def test_all_protected_templates_render(self):
        app = self.application()
        self.login_seeker()
        for name, args in [
            ("jobseeker_dashboard", []),
            ("applications", []),
            ("saved_jobs", []),
            ("edit_application", [app.pk]),
        ]:
            with self.subTest(name=name):
                self.assertEqual(
                    self.client.get(
                        reverse("dashboard:" + name, args=args)
                    ).status_code,
                    200,
                )
        self.login_employer()
        for name, args in [
            ("employer_dashboard", []),
            ("manage_jobs", []),
            ("employer_applications", []),
            ("candidate_detail", [app.pk]),
        ]:
            with self.subTest(name=name):
                self.assertEqual(
                    self.client.get(
                        reverse("dashboard:" + name, args=args)
                    ).status_code,
                    200,
                )

    def test_employer_stats_are_not_limited_to_recent_five(self):
        for i in range(7):
            job = Job.objects.create(
                title=f"Test role {i}",
                employer=self.employer,
                description="Test",
                requirements="Test",
                location="Remote",
                salary="₹5 LPA",
                job_type="full_time",
            )
            Application.objects.create(
                job=job,
                job_seeker=self.seeker,
                status="pending" if i < 6 else "accepted",
            )
        self.login_employer()
        r = self.client.get(reverse("dashboard:employer_dashboard"))
        self.assertEqual(r.context["stats"]["total"], 7)
        self.assertEqual(r.context["stats"]["pending"], 6)
        self.assertEqual(r.context["stats"]["accepted"], 1)
        self.assertEqual(len(r.context["recent_applications"]), 5)
        self.assertEqual(r.context["active_jobs"], 8)

    def test_employer_cannot_view_change_or_download_other_employer_application(self):
        app = self.application()
        app.resume.save("snapshot.pdf", pdf_upload())
        self.client.force_login(self.other_employer_user)
        for name in ["candidate_detail", "application_resume"]:
            self.assertEqual(
                self.client.get(
                    reverse("dashboard:" + name, args=[app.pk])
                ).status_code,
                404,
            )
        self.assertEqual(
            self.client.post(
                reverse("dashboard:manage_application", args=[app.pk]),
                {"status": "accepted"},
            ).status_code,
            404,
        )
        app.refresh_from_db()
        self.assertEqual(app.status, "pending")

    def test_seeker_cannot_edit_withdraw_or_download_another_application(self):
        app = self.application()
        self.client.force_login(self.other_seeker_user)
        self.assertEqual(
            self.client.get(
                reverse("dashboard:edit_application", args=[app.pk])
            ).status_code,
            404,
        )
        self.assertEqual(
            self.client.post(
                reverse("dashboard:withdraw_application", args=[app.pk])
            ).status_code,
            404,
        )
        self.assertEqual(
            self.client.get(
                reverse("dashboard:application_resume", args=[app.pk])
            ).status_code,
            404,
        )
        self.assertEqual(
            self.client.get(
                reverse("dashboard:candidate_detail", args=[app.pk])
            ).status_code,
            403,
        )

    def test_status_update_is_visible_to_candidate(self):
        app = self.application()
        self.login_employer()
        url = reverse("dashboard:manage_application", args=[app.pk])
        self.assertEqual(self.client.get(url).status_code, 405)
        for status in ["reviewing", "shortlisted", "interview", "accepted", "rejected"]:
            self.assertEqual(self.client.post(url, {"status": status}).status_code, 302)
            app.refresh_from_db()
            self.assertEqual(app.status, status)
        self.login_seeker()
        self.assertContains(
            self.client.get(reverse("dashboard:applications")), "Rejected"
        )

    def test_invalid_status_rejected_without_change(self):
        app = self.application()
        self.login_employer()
        self.assertEqual(
            self.client.post(
                reverse("dashboard:manage_application", args=[app.pk]),
                {"status": "hacked"},
            ).status_code,
            400,
        )
        app.refresh_from_db()
        self.assertEqual(app.status, "pending")

    def test_edit_eligibility(self):
        app = self.application(cover_letter="Before")
        self.login_seeker()
        url = reverse("dashboard:edit_application", args=[app.pk])
        self.client.post(url, {"cover_letter": "After"})
        app.refresh_from_db()
        self.assertEqual(app.cover_letter, "After")
        app.status = "reviewing"
        app.save()
        self.client.post(url, {"cover_letter": "Not allowed"})
        app.refresh_from_db()
        self.assertEqual(app.cover_letter, "After")

    def test_withdraw_preserves_history_and_cannot_be_reopened(self):
        app = self.application(status="reviewing")
        self.login_seeker()
        url = reverse("dashboard:withdraw_application", args=[app.pk])
        self.assertEqual(self.client.get(url).status_code, 405)
        self.client.post(url)
        app.refresh_from_db()
        self.assertEqual(app.status, "withdrawn")
        self.assertEqual(Application.objects.count(), 1)
        self.login_employer()
        self.client.post(
            reverse("dashboard:manage_application", args=[app.pk]),
            {"status": "accepted"},
        )
        app.refresh_from_db()
        self.assertEqual(app.status, "withdrawn")
        self.assertEqual(
            self.client.get(
                reverse("dashboard:application_resume", args=[app.pk])
            ).status_code,
            404,
        )

    def test_accepted_application_cannot_be_withdrawn(self):
        app = self.application(status="accepted")
        self.login_seeker()
        self.client.post(reverse("dashboard:withdraw_application", args=[app.pk]))
        app.refresh_from_db()
        self.assertEqual(app.status, "accepted")

    def test_resume_access_is_scoped_and_not_cached(self):
        app = self.application()
        app.resume.save("snapshot.pdf", pdf_upload())
        self.login_employer()
        r = self.client.get(reverse("dashboard:application_resume", args=[app.pk]))
        self.assertEqual(r.status_code, 200)
        self.assertEqual(r["Cache-Control"], "private, no-store")
        r.close()
        self.login_seeker()
        r = self.client.get(reverse("dashboard:application_resume", args=[app.pk]))
        self.assertEqual(r.status_code, 200)
        r.close()
        self.client.logout()
        self.assertEqual(
            self.client.get(
                reverse("dashboard:application_resume", args=[app.pk])
            ).status_code,
            302,
        )

    def test_filtering_and_stats_only_include_owned_records(self):
        self.application(status="shortlisted")
        job = Job.objects.create(
            title="Other job",
            employer=self.other_employer,
            description="Test",
            requirements="Test",
            location="Remote",
            salary="₹5 LPA",
            job_type="full_time",
        )
        Application.objects.create(
            job=job, job_seeker=self.other_seeker, status="accepted"
        )
        self.login_employer()
        r = self.client.get(
            reverse("dashboard:employer_applications"),
            {"status": "shortlisted", "job": self.job.pk},
        )
        self.assertEqual(r.context["page_obj"].paginator.count, 1)
        r = self.client.get(reverse("dashboard:employer_applications"), {"job": job.pk})
        self.assertEqual(r.context["page_obj"].paginator.count, 0)
        self.assertTrue(r.context["form"].errors)
        self.login_seeker()
        r = self.client.get(reverse("dashboard:jobseeker_dashboard"))
        self.assertEqual(r.context["stats"]["total"], 1)
        self.assertEqual(r.context["stats"]["shortlisted"], 1)
        self.assertEqual(r.context["stats"]["accepted"], 0)

    def test_applied_seeker_can_still_view_deactivated_job(self):
        self.application()
        self.job.is_active = False
        self.job.save()
        self.login_seeker()
        self.assertEqual(self.client.get(self.job.get_absolute_url()).status_code, 200)
        self.client.force_login(self.other_seeker_user)
        self.assertEqual(self.client.get(self.job.get_absolute_url()).status_code, 404)
