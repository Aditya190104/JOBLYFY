from django.urls import reverse
from core.test_support import PortalTestCase
from apps.jobs.models import Application, Job
from .insights import application_insights


class ApplicationInsightsTests(PortalTestCase):
    def make_application(self, status, employer=None, seeker=None):
        job = Job.objects.create(
            title="Test insight", employer=employer or self.employer,
            description="Test", requirements="Test", location="Remote",
        )
        return Application.objects.create(
            job=job, job_seeker=seeker or self.seeker, status=status,
        )

    def test_distribution_counts_all_statuses_beyond_recent_five(self):
        for status, _ in Application.STATUS_CHOICES:
            self.make_application(status)
        self.make_application("pending")
        self.login_seeker()
        response = self.client.get(reverse("dashboard:jobseeker_dashboard"))
        rows = response.context["status_distribution"]
        self.assertEqual(response.context["stats"]["total"], 8)
        self.assertEqual(sum(row["count"] for row in rows), 8)
        self.assertEqual(rows[0]["count"], 2)
        self.assertEqual(rows[0]["percent"], 25)
        self.assertEqual(len(response.context["applications"]), 5)
        for status, _ in Application.STATUS_CHOICES:
            self.assertContains(response, "?status=" + status)

    def test_both_dashboard_charts_obey_ownership(self):
        self.make_application("accepted")
        self.make_application("rejected", seeker=self.other_seeker)
        self.make_application("pending", employer=self.other_employer, seeker=self.other_seeker)
        self.login_seeker()
        response = self.client.get(reverse("dashboard:jobseeker_dashboard"))
        self.assertEqual(response.context["stats"]["total"], 1)
        self.assertEqual(response.context["stats"]["rejected"], 0)
        self.login_employer()
        response = self.client.get(reverse("dashboard:employer_dashboard"))
        self.assertEqual(response.context["stats"]["total"], 2)
        self.assertEqual(response.context["stats"]["pending"], 0)

    def test_empty_distribution_has_no_fabricated_values(self):
        for login, name in [(self.login_seeker, "jobseeker_dashboard"),
                            (self.login_employer, "employer_dashboard")]:
            login()
            response = self.client.get(reverse("dashboard:" + name))
            self.assertEqual(response.context["stats"]["total"], 0)
            self.assertTrue(all(row["count"] == row["percent"] == 0
                                for row in response.context["status_distribution"]))
            self.assertContains(response, "A clear picture starts with one application.")
            self.assertNotContains(response, 'class="chart-bar"')

    def test_legacy_status_is_counted_and_query_is_bounded(self):
        self.make_application("older-status")
        with self.assertNumQueries(1):
            stats, rows = application_insights(Application.objects.filter(job_seeker=self.seeker))
        self.assertEqual(stats["total"], 1)
        self.assertEqual(rows[-1], {
            "status": "other", "label": "Other / legacy", "count": 1, "percent": 100,
        })

    def test_recruiter_status_update_changes_both_distributions(self):
        application = self.make_application("pending")
        self.login_employer()
        self.client.post(reverse("dashboard:manage_application", args=[application.pk]),
                         {"status": "shortlisted"})
        for login, name in [(self.login_seeker, "jobseeker_dashboard"),
                            (self.login_employer, "employer_dashboard")]:
            login()
            response = self.client.get(reverse("dashboard:" + name))
            self.assertEqual(response.context["stats"]["pending"], 0)
            self.assertEqual(response.context["stats"]["shortlisted"], 1)
