from django.contrib import admin
from django.test import RequestFactory
from django.urls import reverse
from core.test_support import PortalTestCase
from .models import CompanyReview
from .admin import CompanyReviewAdmin


class CompanyReviewTests(PortalTestCase):
    def data(self, **changes):
        data = {
            "rating": "4",
            "relationship": "former",
            "title": "Thoughtful collaboration",
            "body": "I enjoyed collaborating with this team and appreciated the clear expectations and helpful feedback.",
            "consent": "on",
        }
        data.update(changes)
        return data

    def test_submission_is_private_until_moderated_and_edit_requeues(self):
        url = reverse("jobs:company_review", args=[self.employer.pk])
        self.login_seeker()
        self.assertEqual(self.client.get(url).status_code, 200)
        self.assertRedirects(
            self.client.post(url, self.data()), self.employer.get_absolute_url()
        )
        review = CompanyReview.objects.get()
        self.assertEqual(review.author, self.seeker)
        self.assertEqual(review.status, "pending")
        self.client.logout()
        self.assertNotContains(
            self.client.get(self.employer.get_absolute_url()),
            "Thoughtful collaboration",
        )
        CompanyReview.objects.filter(pk=review.pk).update(status="approved")
        response = self.client.get(self.employer.get_absolute_url())
        self.assertContains(response, "Thoughtful collaboration")
        self.assertNotContains(response, "candidate@example.invalid")
        self.assertEqual(response.context["company"].average_rating, 4)
        self.assertEqual(response.context["company"].review_count, 1)
        self.login_seeker()
        self.client.post(url, self.data(title="Updated experience"))
        review.refresh_from_db()
        self.assertEqual(review.status, "pending")
        self.assertEqual(CompanyReview.objects.count(), 1)

    def test_validation_role_csrf_and_review_ownership(self):
        url = reverse("jobs:company_review", args=[self.employer.pk])
        self.assertEqual(self.client.get(url).status_code, 302)
        self.login_employer()
        self.assertEqual(self.client.post(url, self.data()).status_code, 403)
        self.login_seeker()
        for values in [
            dict(rating="6"),
            dict(body="Short"),
            dict(consent=""),
            dict(relationship="fake"),
        ]:
            self.client.post(url, self.data(**values))
            self.assertFalse(CompanyReview.objects.exists())
        self.client.post(url, self.data())
        review = CompanyReview.objects.get()
        self.client.force_login(self.other_seeker_user)
        self.assertEqual(
            self.client.post(
                reverse("jobs:remove_review", args=[review.pk])
            ).status_code,
            404,
        )
        self.login_seeker()
        self.assertEqual(
            self.client.get(
                reverse("jobs:remove_review", args=[review.pk])
            ).status_code,
            405,
        )
        from django.test import Client

        strict = Client(enforce_csrf_checks=True)
        strict.force_login(self.seeker_user)
        self.assertEqual(strict.post(url, self.data()).status_code, 403)
        self.client.post(reverse("jobs:remove_review", args=[review.pk]))
        self.assertFalse(CompanyReview.objects.exists())

    def test_salary_insights_exclude_samples_closed_and_free_text(self):
        self.job.salary_min = 500000
        self.job.salary_max = 900000
        self.job.save()
        response = self.client.get(self.employer.get_absolute_url())
        self.assertEqual(response.context["salary_insights"]["count"], 1)
        self.job.is_demo = True
        self.job.save()
        self.assertEqual(
            self.client.get(self.employer.get_absolute_url()).context[
                "salary_insights"
            ]["count"],
            0,
        )

    def test_admin_moderation_and_employer_separation(self):
        review = CompanyReview.objects.create(
            employer=self.employer,
            author=self.seeker,
            rating=5,
            relationship="current",
            title="Test review",
            body="A detailed own experience.",
        )
        site = CompanyReviewAdmin(CompanyReview, admin.site)
        request = RequestFactory().get("/admin/")
        request.user = self.employer_user
        self.employer_user.is_staff = True
        self.employer_user.is_superuser = True
        self.assertFalse(site.has_change_permission(request, review))
        from apps.accounts.models import CustomUser

        moderator = CustomUser.objects.create_superuser(
            "moderator", "moderator@example.invalid", "long-test-password"
        )
        request.user = moderator
        self.assertTrue(site.has_change_permission(request, review))
        site.approve_reviews(request, CompanyReview.objects.filter(pk=review.pk))
        review.refresh_from_db()
        self.assertEqual(review.status, "approved")
        self.assertIsNotNone(review.moderated_at)
        site.reject_reviews(request, CompanyReview.objects.filter(pk=review.pk))
        review.refresh_from_db()
        self.assertEqual(review.status, "rejected")

    def test_rating_aggregate_is_not_multiplied_by_job_count(self):
        from .models import Job

        for i in range(3):
            Job.objects.create(
                employer=self.employer,
                title=f"Role{i}",
                description="Test",
                requirements="Test",
                location="Mohali",
                job_type="full_time",
            )
        for author, rating in [(self.seeker, 2), (self.other_seeker, 4)]:
            CompanyReview.objects.create(
                employer=self.employer,
                author=author,
                rating=rating,
                relationship="former",
                title="Own experience",
                body="Test",
                status="approved",
            )
        company = self.client.get(self.employer.get_absolute_url()).context["company"]
        self.assertEqual(company.review_count, 2)
        self.assertEqual(company.average_rating, 3)
        self.assertEqual(company.open_count, 4)
