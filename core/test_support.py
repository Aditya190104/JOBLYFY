"""Isolated test fixtures: never used as application seed data."""

import tempfile
from datetime import timedelta
from io import BytesIO
from django.core.cache import cache
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase, override_settings
from django.utils import timezone
from pypdf import PdfWriter
from apps.accounts.models import CustomUser, Employer, JobSeeker
from apps.jobs.models import Category, Job


def pdf_upload(name="resume.pdf"):
    stream = BytesIO()
    writer = PdfWriter()
    writer.add_blank_page(width=612, height=792)
    writer.write(stream)
    return SimpleUploadedFile(name, stream.getvalue(), content_type="application/pdf")


@override_settings(
    PASSWORD_HASHERS=["django.contrib.auth.hashers.MD5PasswordHasher"],
    CACHES={"default": {"BACKEND": "django.core.cache.backends.locmem.LocMemCache"}},
    EMAIL_BACKEND="django.core.mail.backends.locmem.EmailBackend",
    SECURE_SSL_REDIRECT=False,
    SESSION_COOKIE_SECURE=False,
    CSRF_COOKIE_SECURE=False,
)
class PortalTestCase(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.employer_user = CustomUser.objects.create_user(
            "hiring",
            "hiring@example.invalid",
            "Strong-pass-278!",
            is_employer=True,
            first_name="Hiring",
        )
        cls.employer = Employer.objects.create(
            user=cls.employer_user,
            company_name="Test Company",
            company_description="Test description",
            location="Mohali",
        )
        cls.other_employer_user = CustomUser.objects.create_user(
            "other-hiring",
            "other-hiring@example.invalid",
            "Strong-pass-278!",
            is_employer=True,
        )
        cls.other_employer = Employer.objects.create(
            user=cls.other_employer_user, company_name="Other Test Company"
        )
        cls.seeker_user = CustomUser.objects.create_user(
            "candidate",
            "candidate@example.invalid",
            "Strong-pass-278!",
            is_job_seeker=True,
            first_name="Candidate",
        )
        cls.seeker = JobSeeker.objects.create(
            user=cls.seeker_user,
            skills="Python, Django",
            education="B.Tech",
            location="Ludhiana",
        )
        cls.other_seeker_user = CustomUser.objects.create_user(
            "other-candidate",
            "other-candidate@example.invalid",
            "Strong-pass-278!",
            is_job_seeker=True,
        )
        cls.other_seeker = JobSeeker.objects.create(user=cls.other_seeker_user)
        cls.category = Category.objects.create(name="Technology", icon="fas fa-code")
        cls.job = Job.objects.create(
            title="Django Developer",
            employer=cls.employer,
            category=cls.category,
            description="Build learning tools with Python",
            requirements="Python and Django",
            location="Mohali",
            salary="₹6–9 LPA",
            job_type="full_time",
            work_mode="hybrid",
            deadline=timezone.localdate() + timedelta(days=30),
        )

    def setUp(self):
        self.media = tempfile.TemporaryDirectory()
        self.media_override = override_settings(MEDIA_ROOT=self.media.name)
        self.media_override.enable()
        cache.clear()

    def tearDown(self):
        self.media_override.disable()
        self.media.cleanup()

    def login_seeker(self):
        self.client.force_login(self.seeker_user)

    def login_employer(self):
        self.client.force_login(self.employer_user)

    def prepare_application(
        self, values=None, *, job=None, candidate=None, answers=None
    ):
        """Drive the real reviewed application flow without bypassing backend checks."""
        from django.urls import reverse
        from apps.jobs.models import ApplicationDraft

        job, values = job or self.job, values or {}
        url = reverse("jobs:application_start", args=[job.pk])
        draft = ApplicationDraft.objects.filter(job=job, job_seeker=self.seeker).first()
        response = self.client.post(
            url,
            {
                "step": "eligibility",
                "action": "continue",
                "draft_version": draft.version if draft else 0,
                **(candidate or {}),
            },
        )
        self.assertEqual(response.status_code, 302)
        draft = ApplicationDraft.objects.get(job=job, job_seeker=self.seeker)
        response = self.client.post(
            url,
            {"step": "questions", "draft_version": draft.version, **(answers or {})},
        )
        self.assertEqual(response.status_code, 302)
        draft.refresh_from_db()
        response = self.client.post(
            url,
            {
                "step": "resume",
                "draft_version": draft.version,
                "resume_source": "upload" if values.get("resume") else "profile",
                **values,
            },
        )
        self.assertEqual(response.status_code, 302)
        review = self.client.get(url + "?step=review")
        self.assertEqual(review.status_code, 200)
        return review

    def submit_application(
        self, values=None, *, job=None, candidate=None, answers=None, follow=False
    ):
        from django.urls import reverse

        review = self.prepare_application(
            values, job=job, candidate=candidate, answers=answers
        )
        return self.client.post(
            reverse("jobs:apply_job", args=[(job or self.job).pk]),
            {
                "review_token": review.context["final_form"].initial["review_token"],
                "consent": "on",
            },
            follow=follow,
        )
