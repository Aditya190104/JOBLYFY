from datetime import timedelta
from django.test import Client
from django.urls import reverse
from django.utils import timezone
from core.test_support import PortalTestCase
from .models import SavedJob


class SavedJobInteractionTests(PortalTestCase):
    def setUp(self):
        super().setUp()
        self.url = reverse("jobs:save_job", args=[self.job.pk])
        self.login_seeker()

    def post(self, intent, **kwargs):
        return self.client.post(self.url, {"intent": intent}, HTTP_ACCEPT="application/json", **kwargs)

    def test_explicit_save_and_remove_are_idempotent(self):
        for _ in range(2):
            response = self.post("save")
            self.assertEqual(response.status_code, 200)
            self.assertEqual(response.json()["job_id"], self.job.pk)
            self.assertTrue(response.json()["saved"])
        self.assertEqual(SavedJob.objects.count(), 1)
        for _ in range(2):
            self.assertFalse(self.post("remove").json()["saved"])
        self.assertEqual(SavedJob.objects.count(), 0)

    def test_invalid_or_ambiguous_json_intent_cannot_toggle(self):
        self.post("save")
        for value in ["", "toggle", "SAVE", "other"]:
            self.assertEqual(self.post(value).status_code, 400)
        self.assertEqual(SavedJob.objects.count(), 1)

    def test_closed_expired_and_paused_jobs_reject_new_save(self):
        for changes in [
            {"is_active": False},
            {"is_active": True, "deadline": timezone.localdate() - timedelta(days=1)},
            {"deadline": None, "publication_status": "paused"},
        ]:
            for field, value in changes.items():
                setattr(self.job, field, value)
            self.job.save()
            response = self.post("save")
            self.assertEqual(response.status_code, 409)
            self.assertFalse(response.json()["saved"])
        self.assertFalse(SavedJob.objects.exists())

    def test_saved_closed_job_can_still_be_removed(self):
        self.post("save")
        self.job.is_active = False
        self.job.save()
        self.assertTrue(self.post("save").json()["saved"])
        self.assertFalse(self.post("remove").json()["saved"])

    def test_save_is_private_and_role_protected(self):
        self.post("save")
        self.client.force_login(self.other_seeker_user)
        self.post("remove")
        self.assertEqual(SavedJob.objects.get().job_seeker_id, self.seeker.pk)
        self.login_employer()
        self.assertEqual(self.post("save").status_code, 403)
        self.client.logout()
        self.assertEqual(self.post("save").status_code, 302)
        self.assertEqual(SavedJob.objects.count(), 1)

    def test_real_csrf_check_and_post_only_remain_enforced(self):
        client = Client(enforce_csrf_checks=True)
        client.force_login(self.seeker_user)
        self.assertEqual(client.get(self.url).status_code, 405)
        self.assertEqual(client.post(self.url, {"intent": "save"},
                                    HTTP_ACCEPT="application/json").status_code, 403)
        client.get(reverse("jobs:job_detail", args=[self.job.pk]))
        response = client.post(self.url, {
            "intent": "save", "csrfmiddlewaretoken": client.cookies["csrftoken"].value,
        }, HTTP_ACCEPT="application/json")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response["Cache-Control"], "private, no-store")

    def test_html_fallback_and_legacy_toggle_keep_working(self):
        for value in ["save", "save"]:
            response = self.client.post(self.url, {"intent": value, "next": "/jobs/"})
            self.assertRedirects(response, "/jobs/")
        self.assertEqual(SavedJob.objects.count(), 1)
        response = self.client.post(self.url, {"next": "https://untrusted.example/"})
        self.assertRedirects(response, reverse("dashboard:saved_jobs"))
        self.assertFalse(SavedJob.objects.exists())
