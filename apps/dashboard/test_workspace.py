from django.urls import reverse
from core.test_support import PortalTestCase, pdf_upload
from apps.accounts.models import JobPreference
from apps.jobs.models import Application
from .models import Notification


class WorkspaceEnhancementTests(PortalTestCase):
    def test_preference_save_and_dashboard_matching(self):
        self.login_seeker()
        url = reverse("accounts:job_preferences")
        self.assertEqual(self.client.get(url).status_code, 200)
        self.client.post(
            url,
            {"keywords": "Python", "location": "  SAS Nagar  ", "work_mode": "hybrid"},
        )
        preference = JobPreference.objects.get()
        self.assertEqual(preference.location, "Mohali")
        self.assertEqual(preference.job_seeker, self.seeker)
        response = self.client.get(reverse("dashboard:jobseeker_dashboard"))
        self.assertTrue(response.context["preference_active"])
        self.assertEqual(len(response.context["latest_jobs"]), 1)
        self.client.post(url, {"keywords": "unmatchedkeyword"})
        self.assertEqual(
            len(
                self.client.get(reverse("dashboard:jobseeker_dashboard")).context[
                    "latest_jobs"
                ]
            ),
            0,
        )
        self.assertEqual(JobPreference.objects.count(), 1)
        self.client.post(url, {"keywords": ""})
        self.assertFalse(
            self.client.get(reverse("dashboard:jobseeker_dashboard")).context[
                "preference_active"
            ]
        )
        self.login_employer()
        self.assertEqual(self.client.post(url, {}).status_code, 403)

    def test_invalid_preferences_do_not_create_unusable_filters(self):
        self.login_seeker()
        for values in [
            {"min_salary": 100000001},
            {"keywords": " ".join(["word"] * 13)},
        ]:
            response = self.client.post(reverse("accounts:job_preferences"), values)
            self.assertTrue(response.context["form"].errors)
            self.assertFalse(JobPreference.objects.exists())

    def test_notification_lifecycle_and_cross_user_ownership(self):
        self.login_seeker()
        self.submit_application({"resume": pdf_upload()})
        app = Application.objects.get()
        note = Notification.objects.get()
        self.assertEqual(note.recipient, self.employer_user)
        self.assertEqual(
            self.client.post(
                reverse("dashboard:read_notification", args=[note.pk])
            ).status_code,
            404,
        )
        self.login_employer()
        self.assertContains(
            self.client.get(reverse("dashboard:notifications")), "New application"
        )
        self.client.post(reverse("dashboard:read_notification", args=[note.pk]))
        note.refresh_from_db()
        self.assertIsNotNone(note.read_at)
        status_url = reverse("dashboard:manage_application", args=[app.pk])
        self.client.post(status_url, {"status": "shortlisted"})
        self.client.post(status_url, {"status": "shortlisted"})
        self.assertEqual(
            Notification.objects.filter(recipient=self.seeker_user).count(), 1
        )
        self.login_seeker()
        self.assertContains(
            self.client.get(reverse("dashboard:notifications")), "now shortlisted"
        )
        self.assertEqual(
            self.client.get(reverse("dashboard:read_all_notifications")).status_code,
            405,
        )
        self.client.post(reverse("dashboard:read_all_notifications"))
        self.assertFalse(
            Notification.objects.filter(
                recipient=self.seeker_user, read_at__isnull=True
            ).exists()
        )
        self.client.post(reverse("dashboard:withdraw_application", args=[app.pk]))
        self.assertEqual(
            Notification.objects.filter(recipient=self.employer_user).count(), 2
        )

    def test_notifications_and_settings_pages_and_private_caching(self):
        self.login_seeker()
        for name in [
            "dashboard:notifications",
            "accounts:job_preferences",
            "accounts:settings",
        ]:
            response = self.client.get(reverse(name))
            self.assertEqual(response.status_code, 200)
            self.assertEqual(response["Cache-Control"], "private, no-store")
        self.client.post(
            reverse("accounts:settings"),
            {
                "old_password": "wrong",
                "new_password1": "New-secure-582!",
                "new_password2": "New-secure-582!",
            },
        )
        self.seeker_user.refresh_from_db()
        self.assertFalse(self.seeker_user.check_password("New-secure-582!"))
        response = self.client.post(
            reverse("accounts:settings"),
            {
                "old_password": "Strong-pass-278!",
                "new_password1": "New-secure-582!",
                "new_password2": "New-secure-582!",
            },
            follow=True,
        )
        self.assertEqual(response.status_code, 200)
        self.seeker_user.refresh_from_db()
        self.assertTrue(self.seeker_user.check_password("New-secure-582!"))
        self.assertContains(
            self.client.get(reverse("dashboard:jobseeker_dashboard")), "Welcome back"
        )
