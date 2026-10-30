"""Regression coverage for persistent authentication and the shared UI shell."""

from unittest.mock import patch
from django.conf import settings
from django.core.exceptions import ValidationError
from django.test import Client
from django.urls import reverse
from core.test_support import PortalTestCase
from .forms import EmployerSignUpForm, JobSeekerSignUpForm
from .models import CustomUser, JobSeeker


class PremiumAccountTests(PortalTestCase):
    def test_signup_password_whitespace_is_preserved_on_login(self):
        password = "  Strong-signup-secret-739!  "
        self.client.post(
            reverse("accounts:jobseeker_signup"),
            self.signup_data(
                password1=password,
                password2=password,
            ),
        )
        user = CustomUser.objects.get(username="newmember")
        self.assertTrue(user.check_password(password))
        self.client.post(reverse("accounts:logout"))
        response = self.client.post(
            reverse("accounts:login"),
            {
                "username_or_email": "newmember",
                "password": password,
            },
        )
        self.assertEqual(response.status_code, 302)
        self.assertEqual(int(self.client.session["_auth_user_id"]), user.pk)
        self.client.post(reverse("accounts:logout"))
        self.client.post(
            reverse("accounts:login"),
            {
                "username_or_email": "newmember",
                "password": password.strip(),
            },
        )
        self.assertNotIn("_auth_user_id", self.client.session)

    def signup_data(self, **extra):
        return {
            "username": "newmember",
            "email": "newmember@example.invalid",
            "password1": "Private-testing-548!",
            "password2": "Private-testing-548!",
            **extra,
        }

    def sign_in(self, **extra):
        return self.client.post(
            reverse("accounts:login"),
            {
                "username_or_email": "candidate",
                "password": "Strong-pass-278!",
                **extra,
            },
        )

    def test_signup_session_policy_and_stored_credentials(self):
        self.client.post(reverse("accounts:jobseeker_signup"), self.signup_data())
        self.assertTrue(self.client.session.get_expire_at_browser_close())
        self.assertEqual(
            self.client.cookies[settings.SESSION_COOKIE_NAME]["max-age"], ""
        )
        user = CustomUser.objects.get(username="newmember")
        self.assertTrue(user.check_password(self.signup_data()["password1"]))
        self.client.post(reverse("accounts:logout"))
        self.assertTrue(JobSeeker.objects.filter(user=user).exists())
        response = self.client.post(
            reverse("accounts:login"),
            {
                "username_or_email": user.email.upper(),
                "password": self.signup_data()["password1"],
            },
            follow=True,
        )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(int(self.client.session["_auth_user_id"]), user.pk)

    def test_database_session_survives_new_client_and_page_refresh(self):
        self.sign_in(remember="on")
        self.assertFalse(self.client.session.get_expire_at_browser_close())
        self.assertEqual(
            int(self.client.cookies[settings.SESSION_COOKIE_NAME]["max-age"]), 1209600
        )
        fresh_client = Client()
        fresh_client.cookies = self.client.cookies
        for route in (
            "dashboard:jobseeker_dashboard",
            "accounts:user_profile",
            "dashboard:saved_jobs",
            "dashboard:applications",
            "accounts:settings",
        ):
            for _ in range(2):
                response = fresh_client.get(reverse(route))
                self.assertEqual(response.status_code, 200)
                self.assertEqual(response.wsgi_request.user.pk, self.seeker_user.pk)
                self.assertIn("no-store", response["Cache-Control"])

    def test_unambiguous_case_insensitive_username_and_exact_legacy_priority(self):
        self.sign_in(username_or_email="CANDIDATE")
        self.assertEqual(int(self.client.session["_auth_user_id"]), self.seeker_user.pk)
        self.client.logout()
        other = CustomUser.objects.create_user(
            username="Candidate", password="Separate-private-617!"
        )
        response = self.sign_in(
            username_or_email="Candidate", password="Separate-private-617!"
        )
        self.assertEqual(response.status_code, 302)
        self.assertEqual(int(self.client.session["_auth_user_id"]), other.pk)
        self.client.logout()
        self.sign_in(username_or_email="CANDIDATE")
        self.assertNotIn("_auth_user_id", self.client.session)

    def test_registration_rechecks_identity_after_prior_validation(self):
        # Simulates two already-validated requests competing for the same identity.
        for form_class in (JobSeekerSignUpForm, EmployerSignUpForm):
            for collision in ("email", "username"):
                with self.subTest(form=form_class.__name__, collision=collision):
                    data = self.signup_data(company_name="Test team")
                    pending = form_class(data)
                    self.assertTrue(pending.is_valid(), pending.errors)
                    competing = CustomUser.objects.create_user(
                        username=data["username"].upper()
                        if collision == "username"
                        else "competing",
                        email=data["email"].upper()
                        if collision == "email"
                        else "separate@example.invalid",
                        password="Separate-private-617!",
                    )
                    before = CustomUser.objects.count()
                    with self.assertRaises(ValidationError) as caught:
                        pending.save()
                    self.assertIn(collision, caught.exception.message_dict)
                    self.assertEqual(CustomUser.objects.count(), before)
                    competing.delete()

    def test_race_validation_is_rendered_as_field_error(self):
        with patch.object(
            JobSeekerSignUpForm,
            "save",
            side_effect=ValidationError({"email": ["This email is already in use."]}),
        ):
            response = self.client.post(
                reverse("accounts:jobseeker_signup"), self.signup_data()
            )
        self.assertContains(response, "This email is already in use.")
        self.assertFalse(CustomUser.objects.filter(username="newmember").exists())

    def test_profile_rejects_another_accounts_email_without_partial_write(self):
        self.login_seeker()
        response = self.client.post(
            reverse("accounts:user_profile"),
            {
                "user-first_name": "Should not persist",
                "user-email": self.other_seeker_user.email.upper(),
                "profile-headline": "Should not persist",
            },
        )
        self.assertContains(response, "This email is already in use.")
        self.seeker_user.refresh_from_db()
        self.seeker.refresh_from_db()
        self.assertNotEqual(self.seeker_user.first_name, "Should not persist")
        self.assertNotEqual(self.seeker.headline, "Should not persist")

    def test_legacy_duplicate_email_can_keep_profile_and_login_by_username(self):
        CustomUser.objects.filter(pk=self.other_seeker_user.pk).update(
            email=self.seeker_user.email
        )
        self.login_seeker()
        response = self.client.post(
            reverse("accounts:user_profile"),
            {
                "user-email": self.seeker_user.email,
                "profile-headline": "Persisted introduction",
            },
        )
        self.assertEqual(response.status_code, 302)
        self.client.post(reverse("accounts:logout"))
        self.sign_in()
        self.assertEqual(int(self.client.session["_auth_user_id"]), self.seeker_user.pk)
        self.seeker.refresh_from_db()
        self.assertEqual(self.seeker.headline, "Persisted introduction")

    def test_password_change_keeps_current_session_and_invalidates_other_session(self):
        self.sign_in(remember="on")
        second = Client()
        second.post(
            reverse("accounts:login"),
            {"username_or_email": "candidate", "password": "Strong-pass-278!"},
        )
        response = self.client.post(
            reverse("accounts:settings"),
            {
                "old_password": "Strong-pass-278!",
                "new_password1": "Changed-secure-829!",
                "new_password2": "Changed-secure-829!",
            },
            follow=True,
        )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(
            self.client.get(reverse("accounts:user_profile")).status_code, 200
        )
        self.assertEqual(second.get(reverse("accounts:user_profile")).status_code, 302)
        self.seeker_user.refresh_from_db()
        self.assertTrue(self.seeker_user.check_password("Changed-secure-829!"))

    def test_invalid_login_and_expired_reset_do_not_authenticate(self):
        response = self.sign_in(password="wrong-password")
        self.assertContains(response, "Unable to sign in")
        self.assertNotIn("_auth_user_id", self.client.session)
        response = self.client.get(
            reverse(
                "accounts:password_reset_confirm", args=["invalid", "expired-token"]
            )
        )
        self.assertContains(response, "This link has expired")
        response = self.client.post(
            reverse("accounts:password_reset"), {"email": "invalid"}
        )
        self.assertContains(response, "Enter a valid email address.")

    def test_developer_credit_on_public_auth_and_private_layouts(self):
        pages = [
            "jobs:home",
            "jobs:job_list",
            "jobs:companies",
            "jobs:categories",
            "accounts:login",
            "accounts:password_reset",
        ]
        for route in pages:
            self.assert_credit(self.client.get(reverse(route)))
        self.login_seeker()
        for route in [
            "dashboard:jobseeker_dashboard",
            "accounts:user_profile",
            "dashboard:applications",
            "accounts:settings",
        ]:
            self.assert_credit(self.client.get(reverse(route)))
        self.login_employer()
        self.assert_credit(self.client.get(reverse("dashboard:employer_dashboard")))

    def assert_credit(self, response):
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Designed &amp; Developed by")
        self.assertContains(response, "Aditya Raj")
        self.assertContains(
            response,
            'href="https://www.linkedin.com/in/adityarajtech19/" target="_blank" rel="noopener noreferrer"',
        )
