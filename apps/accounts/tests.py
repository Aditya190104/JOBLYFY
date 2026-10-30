from io import BytesIO
from PIL import Image
from django.contrib.auth.tokens import default_token_generator
from django.core import mail
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import Client
from django.urls import reverse
from django.utils.encoding import force_bytes
from django.utils.http import urlsafe_base64_encode
from core.test_support import PortalTestCase, pdf_upload
from .models import CustomUser, Employer, JobSeeker
from .forms import JobSeekerSignUpForm


class AccountTests(PortalTestCase):
    def signup_data(self, **extra):
        return {
            "username": "newperson",
            "email": "newperson@example.invalid",
            "password1": "New-strong-pass-374!",
            "password2": "New-strong-pass-374!",
            **extra,
        }

    def test_public_auth_routes_render(self):
        for name in [
            "login",
            "signup",
            "employer_signup",
            "jobseeker_signup",
            "password_reset",
            "password_reset_done",
            "password_reset_complete",
        ]:
            with self.subTest(name=name):
                self.assertEqual(
                    self.client.get(reverse("accounts:" + name)).status_code, 200
                )

    def test_seeker_signup_creates_only_seeker_role_and_hashes_password(self):
        r = self.client.post(reverse("accounts:jobseeker_signup"), self.signup_data())
        self.assertRedirects(
            r, reverse("dashboard:home"), fetch_redirect_response=False
        )
        user = CustomUser.objects.get(username="newperson")
        self.assertTrue(user.is_job_seeker)
        self.assertFalse(user.is_employer)
        self.assertTrue(user.check_password("New-strong-pass-374!"))
        self.assertNotEqual(user.password, "New-strong-pass-374!")
        self.assertTrue(JobSeeker.objects.filter(user=user).exists())

    def test_employer_signup_creates_profile_and_renders_dashboard(self):
        response = self.client.post(
            reverse("accounts:employer_signup"),
            self.signup_data(company_name="New Test Co"),
            follow=True,
        )
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "New Test Co")
        user = CustomUser.objects.get(username="newperson")
        self.assertTrue(user.is_employer)
        self.assertFalse(user.is_job_seeker)
        self.assertTrue(Employer.objects.filter(user=user).exists())

    def test_duplicate_email_and_username_case_variants_rejected(self):
        form = JobSeekerSignUpForm(
            self.signup_data(email=self.seeker_user.email.upper())
        )
        self.assertFalse(form.is_valid())
        self.assertIn("email", form.errors)
        form = JobSeekerSignUpForm(
            self.signup_data(username=self.seeker_user.username.upper())
        )
        self.assertFalse(form.is_valid())
        self.assertIn("username", form.errors)

    def test_weak_password_and_empty_signup_show_errors(self):
        r = self.client.post(reverse("accounts:jobseeker_signup"), {})
        self.assertContains(r, "This field is required.")
        form = JobSeekerSignUpForm(self.signup_data(password1="123", password2="123"))
        self.assertFalse(form.is_valid())
        self.assertIn("password2", form.errors)

    def test_username_and_email_login(self):
        for identity in ["candidate", "CANDIDATE@example.invalid"]:
            r = self.client.post(
                reverse("accounts:login"),
                {"username_or_email": identity, "password": "Strong-pass-278!"},
                follow=True,
            )
            self.assertEqual(r.status_code, 200)
            self.assertContains(r, "Welcome back")
            self.client.post(reverse("accounts:logout"))

    def test_legacy_duplicate_email_does_not_crash_and_username_still_works(self):
        CustomUser.objects.filter(pk=self.other_seeker_user.pk).update(
            email=self.seeker_user.email
        )
        r = self.client.post(
            reverse("accounts:login"),
            {
                "username_or_email": self.seeker_user.email,
                "password": "Strong-pass-278!",
            },
        )
        self.assertContains(r, "Unable to sign in")
        r = self.client.post(
            reverse("accounts:login"),
            {"username_or_email": "candidate", "password": "Strong-pass-278!"},
        )
        self.assertEqual(r.status_code, 302)

    def test_inactive_user_denied(self):
        self.seeker_user.is_active = False
        self.seeker_user.save()
        r = self.client.post(
            reverse("accounts:login"),
            {"username_or_email": "candidate", "password": "Strong-pass-278!"},
        )
        self.assertContains(r, "Unable to sign in")
        self.assertNotIn("_auth_user_id", self.client.session)

    def test_login_redirect_is_safe_and_remember_me_is_respected(self):
        r = self.client.post(
            reverse("accounts:login"),
            {
                "username_or_email": "candidate",
                "password": "Strong-pass-278!",
                "next": "https://evil.example/",
                "remember": "on",
            },
        )
        self.assertEqual(r.url, reverse("dashboard:home"))
        self.assertFalse(self.client.session.get_expire_at_browser_close())
        self.client.post(reverse("accounts:logout"))
        r = self.client.post(
            reverse("accounts:login"),
            {
                "username_or_email": "candidate",
                "password": "Strong-pass-278!",
                "next": reverse("jobs:job_list"),
            },
        )
        self.assertEqual(r.url, reverse("jobs:job_list"))
        self.assertTrue(self.client.session.get_expire_at_browser_close())

    def test_logout_requires_post_and_csrf(self):
        self.login_seeker()
        self.assertEqual(self.client.get(reverse("accounts:logout")).status_code, 405)
        strict = Client(enforce_csrf_checks=True)
        strict.force_login(self.seeker_user)
        self.assertEqual(strict.post(reverse("accounts:logout")).status_code, 403)
        self.assertEqual(self.client.post(reverse("accounts:logout")).status_code, 302)
        self.assertNotIn("_auth_user_id", self.client.session)

    def test_login_throttle(self):
        for _ in range(20):
            self.client.post(
                reverse("accounts:login"),
                {"username_or_email": "absent", "password": "invalid"},
            )
        self.assertEqual(
            self.client.post(reverse("accounts:login"), {}).status_code, 429
        )

    def test_profile_edit_and_private_resume(self):
        self.login_seeker()
        data = {
            "user-first_name": "Updated",
            "user-last_name": "Candidate",
            "user-email": self.seeker_user.email,
            "profile-headline": "Frontend developer",
            "profile-location": "Chandigarh",
            "profile-phone": "1234567890",
            "profile-skills": "React, Python",
            "profile-education": "B.Tech",
            "profile-experience": "Internship",
            "profile-bio": "Building useful products",
            "profile-resume": pdf_upload(),
        }
        self.assertEqual(
            self.client.post(reverse("accounts:user_profile"), data).status_code, 302
        )
        self.seeker.refresh_from_db()
        self.assertEqual(self.seeker.headline, "Frontend developer")
        self.assertTrue(self.seeker.resume_available)
        response = self.client.get(reverse("accounts:own_resume"))
        self.assertEqual(response.status_code, 200)
        self.assertIn("attachment", response["Content-Disposition"])
        self.assertEqual(response["Cache-Control"], "private, no-store")
        response.close()
        self.assertEqual(
            self.client.get("/media/" + self.seeker.resume.name).status_code, 404
        )
        self.assertEqual(
            self.client.get(reverse("accounts:user_profile")).status_code, 200
        )
        # Editing other fields with an unchanged file is safe.
        del data["profile-resume"]
        self.assertEqual(
            self.client.post(reverse("accounts:user_profile"), data).status_code, 302
        )

    def test_profile_validation_is_atomic(self):
        self.login_seeker()
        r = self.client.post(
            reverse("accounts:user_profile"),
            {"user-first_name": "ShouldNotSave", "user-email": "bad"},
        )
        self.assertEqual(r.status_code, 200)
        self.seeker_user.refresh_from_db()
        self.assertNotEqual(self.seeker_user.first_name, "ShouldNotSave")

    def test_role_denies_wrong_profile_and_missing_profile(self):
        self.login_seeker()
        self.assertEqual(
            self.client.get(reverse("accounts:employer_profile")).status_code, 403
        )
        self.login_employer()
        self.assertEqual(
            self.client.get(reverse("accounts:user_profile")).status_code, 403
        )
        self.assertEqual(
            self.client.get(reverse("accounts:own_resume")).status_code, 403
        )
        self.employer.delete()
        self.assertEqual(
            self.client.get(reverse("accounts:employer_profile")).status_code, 403
        )

    def test_resume_validation(self):
        bad_files = [
            SimpleUploadedFile("resume.exe", b"data"),
            SimpleUploadedFile("resume.pdf", b"%PDF-not-real"),
            SimpleUploadedFile("resume.pdf", b"x" * (5 * 1024 * 1024 + 1)),
        ]
        for upload in bad_files:
            form = JobSeekerSignUpForm(self.signup_data(), {"resume": upload})
            self.assertFalse(form.is_valid())
            self.assertIn("resume", form.errors)

    def test_employer_profile_and_logo(self):
        self.login_employer()
        stream = BytesIO()
        Image.new("RGB", (32, 32), "purple").save(stream, format="PNG")
        data = {
            "user-email": self.employer_user.email,
            "profile-company_name": "Updated Company",
            "profile-company_description": "New story",
            "profile-company_website": "https://example.com",
            "profile-location": "Mohali",
            "profile-industry": "Technology",
            "profile-company_logo": SimpleUploadedFile(
                "logo.png", stream.getvalue(), content_type="image/png"
            ),
        }
        self.assertEqual(
            self.client.post(reverse("accounts:employer_profile"), data).status_code,
            302,
        )
        self.employer.refresh_from_db()
        self.assertEqual(self.employer.company_name, "Updated Company")
        self.client.logout()
        response = self.client.get(
            reverse("accounts:company_logo", args=[self.employer.pk])
        )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response["Content-Type"], "image/png")
        response.close()

    def test_password_reset_end_to_end_and_token_reuse(self):
        response = self.client.post(
            reverse("accounts:password_reset"), {"email": self.seeker_user.email}
        )
        self.assertRedirects(response, reverse("accounts:password_reset_done"))
        self.assertEqual(len(mail.outbox), 1)
        self.assertIn("/accounts/reset/", mail.outbox[0].body)
        uid = urlsafe_base64_encode(force_bytes(self.seeker_user.pk))
        token = default_token_generator.make_token(self.seeker_user)
        url = reverse("accounts:password_reset_confirm", args=[uid, token])
        response = self.client.get(url)
        self.assertEqual(response.status_code, 302)
        token_url = response.url
        self.assertContains(self.client.get(token_url), "Make it yours again")
        response = self.client.post(
            token_url,
            {
                "new_password1": "Fresh-secret-349!",
                "new_password2": "Fresh-secret-349!",
            },
        )
        self.assertRedirects(response, reverse("accounts:password_reset_complete"))
        self.seeker_user.refresh_from_db()
        self.assertTrue(self.seeker_user.check_password("Fresh-secret-349!"))
        self.assertContains(self.client.get(url), "This link has expired")

    def test_password_reset_unknown_email_has_same_success_response(self):
        r = self.client.post(
            reverse("accounts:password_reset"), {"email": "missing@example.invalid"}
        )
        self.assertRedirects(r, reverse("accounts:password_reset_done"))
        self.assertEqual(len(mail.outbox), 0)

    def test_missing_files_return_404(self):
        self.login_seeker()
        self.assertEqual(
            self.client.get(reverse("accounts:own_resume")).status_code, 404
        )
        self.assertEqual(
            self.client.get(
                reverse("accounts:company_logo", args=[self.employer.pk])
            ).status_code,
            404,
        )
