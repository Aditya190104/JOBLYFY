from datetime import timedelta
from decimal import Decimal
from io import StringIO
from unittest.mock import patch
from django.core.management import call_command, CommandError
from django.db import IntegrityError, transaction
from django.test import override_settings
from django.test.utils import CaptureQueriesContext
from django.db import connection
from django.urls import reverse
from django.utils import timezone
from core.test_support import PortalTestCase, pdf_upload
from apps.accounts.models import CustomUser, Employer
from .models import Job, CompanyReview, Application
from .forms import JobForm
from .locations import normalize_location, resolve_city


class SearchEnhancementTests(PortalTestCase):
    def search(self, **params):
        return self.client.get(reverse("jobs:job_list"), params)

    def add_job(self, **changes):
        data = dict(
            title="React Developer",
            employer=self.employer,
            category=self.category,
            description="Useful products",
            requirements="React JavaScript CSS",
            location="Bangalore, India",
            salary="",
            salary_min=600000,
            salary_max=1000000,
            job_type="full_time",
        )
        data.update(changes)
        return Job.objects.create(**data)

    def ids(self, response):
        return {j.pk for j in response.context["jobs"]}

    def test_city_aliases_case_whitespace_and_state(self):
        job = self.add_job()
        for text in ["Bengaluru", "  bAnGaLoRe  ", "Bengaluru, Karnataka", "Karnataka"]:
            with self.subTest(text=text):
                self.assertEqual(self.ids(self.search(location=text)), {job.pk})
        self.assertEqual(normalize_location("  S.A.S. Nagar "), "Mohali")
        self.assertIsNotNone(resolve_city("New Delhi"))
        self.assertEqual(self.ids(self.search(location="punjab")), {self.job.pk})

    def test_keyword_tokens_match_skills_company_category_and_relevance(self):
        matching = self.add_job(title="Python React Developer", requirements="Django")
        self.assertEqual(self.ids(self.search(search="React Django")), {matching.pk})
        self.assertEqual(
            self.search(search="Test Company").context["page_obj"].paginator.count, 2
        )
        self.assertEqual(
            self.search(search="Technology").context["page_obj"].paginator.count, 2
        )
        self.assertEqual(
            self.search(search="Python", sort="relevance").context["jobs"][0].pk,
            matching.pk,
        )
        self.assertEqual(
            self.search(search="no-such-keyword-xyz")
            .context["page_obj"]
            .paginator.count,
            0,
        )
        self.assertEqual(
            self.search(search="x" * 151).context["page_obj"].paginator.count, 0
        )
        self.assertTrue(self.search(sort="untrusted-sort").context["form"].errors)

    def test_location_suggestions_live_counts_and_unknown_free_text(self):
        self.add_job(location="Bengaluru")
        url = reverse("jobs:location_suggestions")
        r = self.client.get(url, {"q": "bangalore"})
        self.assertEqual(r.json()["results"][0]["value"], "Bengaluru")
        self.assertEqual(r.json()["results"][0]["count"], 1)
        self.assertTrue(
            any(
                x["value"] == "Mohali"
                for x in self.client.get(url, {"q": "Punjab"}).json()["results"]
            )
        )
        custom = self.add_job(location="Zirakpur")
        self.assertEqual(
            self.client.get(url, {"q": "Zirak"}).json()["results"][0]["value"],
            "Zirakpur",
        )
        self.assertIn(custom.pk, self.ids(self.search(location="zirakpur")))
        self.assertEqual(
            self.client.get(url, {"q": "zzzz-no-such-city"}).json()["results"], []
        )
        self.assertEqual(self.client.get(url, {"q": "x" * 101}).status_code, 400)
        self.assertEqual(self.client.post(url).status_code, 405)
        self.assertLessEqual(len(self.client.get(url).json()["results"]), 8)

    def test_remote_city_and_distance_do_not_hide_remote_roles(self):
        remote = self.add_job(location="India", work_mode="remote")
        self.assertEqual(self.ids(self.search(location="Remote")), {remote.pk})
        self.assertEqual(
            self.ids(self.search(location="Ludhiana", work_mode="remote", radius="25")),
            {remote.pk},
        )
        response = self.search(location="Remote", work_mode="onsite")
        self.assertTrue(response.context["form"].errors)

    def test_nearby_query_uses_coordinates_or_approximate_city_centers(self):
        chandigarh = self.add_job(location="Chandigarh")
        ludhiana = self.add_job(location="Ludhiana")
        explicit = self.add_job(
            location="Industrial Area", latitude="30.736292", longitude="76.788398"
        )
        unknown = self.add_job(location="Unknown City")
        ids = self.ids(self.search(location="Mohali", radius="25"))
        self.assertEqual(ids, {self.job.pk, chandigarh.pk, explicit.pk})
        self.assertIn(
            ludhiana.pk, self.ids(self.search(location="Mohali", radius="100"))
        )
        self.assertNotIn(unknown.pk, ids)
        response = self.search(location="Unknown City", radius="25")
        self.assertContains(response, "Choose a supported city suggestion")
        self.assertEqual(response.context["page_obj"].paginator.count, 0)

    def test_salary_band_overlap_excludes_legacy_and_undisclosed(self):
        middle = self.add_job()
        high = self.add_job(salary_min=1500000, salary_max=2500000)
        self.assertEqual(
            self.ids(self.search(min_salary=700000, max_salary=1200000)), {middle.pk}
        )
        self.assertEqual(self.ids(self.search(min_salary=1600000)), {high.pk})
        self.assertEqual(self.ids(self.search(max_salary=700000)), {middle.pk})
        self.assertTrue(self.search(min_salary=-1).context["form"].errors)
        self.assertTrue(self.search(min_salary=9, max_salary=2).context["form"].errors)
        self.assertEqual(self.job.salary, "₹6–9 LPA")
        self.assertEqual(self.job.salary_display, self.job.salary)
        self.assertIn("lakh / year", middle.salary_display)

    def test_posting_age_combined_filters_sorting_and_pagination(self):
        for i in range(12):
            self.add_job(title=f"Job {i:02d}")
        old = self.add_job(title="Ancient role")
        Job.objects.filter(pk=old.pk).update(
            posted_date=timezone.now() - timedelta(days=45)
        )
        self.assertNotIn(old.pk, self.ids(self.search(posted="7")))
        query = dict(
            search="Job",
            location="Bengaluru",
            job_type="full_time",
            experience="entry",
            work_mode="onsite",
            category=self.category.pk,
            company=self.employer.pk,
            min_salary=500000,
            posted="7",
            sort="title",
        )
        response = self.search(**query)
        self.assertEqual(response.context["page_obj"].paginator.count, 12)
        self.assertEqual(len(response.context["jobs"]), 9)
        self.assertEqual(response.context["jobs"][0].title, "Job 00")
        self.assertEqual(len(self.search(**query, page="2").context["jobs"]), 3)
        self.assertContains(response, "location=Bengaluru")
        self.assertEqual(self.search(page="garbage").status_code, 200)
        self.assertEqual(self.search(page="999999999999999").status_code, 200)

    def test_filters_are_removable_without_discarding_other_values(self):
        response = self.search(
            search="Python",
            location="Mohali",
            radius="25",
            work_mode="hybrid",
            selected=self.job.pk,
            page="2",
        )
        chips = response.context["filter_chips"]
        location = next(c for c in chips if c["label"].startswith("Location"))
        self.assertIn("search=Python", location["url"])
        self.assertNotIn("radius=", location["url"])
        self.assertNotIn("page=", location["url"])
        keyword = next(c for c in chips if c["label"].startswith("Keyword"))
        self.assertIn("location=Mohali", keyword["url"])

    def test_preview_never_exposes_a_job_outside_the_results(self):
        closed = self.add_job(is_active=False)
        response = self.search(selected=closed.pk)
        self.assertEqual(response.context["selected_job"].pk, self.job.pk)
        self.assertIsNone(
            self.search(search="nothinghere", selected=self.job.pk).context[
                "selected_job"
            ]
        )

    def test_job_form_validates_salary_coordinates_and_retains_legacy_description(self):
        data = {
            "title": "Test role",
            "description": "Useful work",
            "requirements": "Python",
            "location": "Bangalore",
            "category": self.category.pk,
            "job_type": "full_time",
            "work_mode": "hybrid",
            "experience_level": "entry",
            "salary": "₹40,000 per month",
            "salary_min": "600000",
            "salary_max": "900000",
        }
        form = JobForm(data)
        self.assertTrue(form.is_valid(), form.errors)
        self.assertEqual(form.cleaned_data["location"], "Bengaluru")
        for invalid in [
            {"salary_max": "100"},
            {"salary_max": ""},
            {"latitude": "91", "longitude": "76"},
            {"latitude": "30", "longitude": ""},
        ]:
            f = JobForm({**data, **invalid})
            self.assertFalse(f.is_valid(), invalid)
        self.login_employer()
        self.client.post(
            reverse("jobs:post_job"), {**data, "latitude": "30.7", "longitude": "76.7"}
        )
        job = Job.objects.get(title="Test role")
        self.assertEqual(job.salary, data["salary"])
        self.assertEqual(job.salary_min, Decimal("600000"))
        self.assertContains(
            self.client.get(job.get_absolute_url()), "Load workplace map"
        )
        self.assertContains(
            self.client.get(job.get_absolute_url()),
            "openstreetmap.org/export/embed.html",
        )
        self.assertNotContains(
            self.client.get(self.job.get_absolute_url()), "Load workplace map"
        )

    def test_database_constraints_protect_salary_and_coordinate_ranges(self):
        for values in [
            {"salary_min": 500, "salary_max": 100},
            {"salary_min": 100, "salary_max": None},
            {"latitude": 91, "longitude": 1},
            {"latitude": 1, "longitude": None},
        ]:
            with (
                self.subTest(values=values),
                self.assertRaises(IntegrityError),
                transaction.atomic(),
            ):
                self.add_job(**values)

    def test_save_returns_to_safe_search_url_and_rejects_external_redirect(self):
        self.login_seeker()
        url = reverse("jobs:save_job", args=[self.job.pk])
        self.assertRedirects(
            self.client.post(url, {"next": "/jobs/?search=Django"}),
            "/jobs/?search=Django",
        )
        self.assertRedirects(
            self.client.post(url, {"next": "https://evil.example/"}),
            reverse("dashboard:saved_jobs"),
        )

    def test_home_uses_real_counts_and_featured_flag(self):
        self.job.is_featured = True
        self.job.save()
        with override_settings(DEBUG=True):
            self.add_job(is_demo=True)
            response = self.client.get("/")
            self.assertEqual(response.context["job_count"], 1)
            self.assertEqual(response.context["sample_job_count"], 1)
            self.assertEqual(
                [j.pk for j in response.context["featured_jobs"]], [self.job.pk]
            )
            self.assertEqual(len(response.context["recent_jobs"]), 2)

    def test_samples_visible_only_in_debug_and_cannot_accept_applications(self):
        demo = self.add_job(is_demo=True)
        with override_settings(DEBUG=False):
            self.assertNotIn(demo.pk, self.ids(self.search()))
            self.assertEqual(self.client.get(demo.get_absolute_url()).status_code, 404)
        with override_settings(DEBUG=True):
            self.assertIn(demo.pk, self.ids(self.search()))
            self.assertContains(
                self.client.get(demo.get_absolute_url()), "not a real vacancy"
            )
            self.login_seeker()
            self.client.post(
                reverse("jobs:apply_job", args=[demo.pk]), {"resume": pdf_upload()}
            )
            self.assertFalse(Application.objects.exists())

    def test_demo_command_is_safe_idempotent_and_production_guarded(self):
        before = list(CustomUser.objects.values("pk", "username", "password"))
        original = Job.objects.values().get(pk=self.job.pk)
        with override_settings(DEBUG=False), self.assertRaises(CommandError):
            call_command("seed_demo", stdout=StringIO())
        with (
            override_settings(DEBUG=True),
            patch(
                "apps.accounts.management.commands.backup_database.Command.handle",
                return_value=None,
            ) as backup,
        ):
            call_command("seed_demo", stdout=StringIO())
            call_command("seed_demo", stdout=StringIO())
            self.assertEqual(backup.call_count, 2)
            self.assertEqual(Job.objects.filter(is_demo=True).count(), 18)
            self.assertEqual(Employer.objects.filter(is_demo=True).count(), 3)
            self.assertFalse(
                any(
                    c.user.has_usable_password()
                    for c in Employer.objects.filter(is_demo=True)
                )
            )
            self.assertFalse(CompanyReview.objects.exists())
            self.assertFalse(Application.objects.exists())
            call_command("seed_demo", deactivate=True, stdout=StringIO())
            self.assertEqual(
                Job.objects.filter(is_demo=True, is_active=True).count(), 0
            )
        self.assertEqual(
            list(
                CustomUser.objects.filter(pk__in=[u["pk"] for u in before]).values(
                    "pk", "username", "password"
                )
            ),
            before,
        )
        self.assertEqual(Job.objects.values().get(pk=self.job.pk), original)

    def test_demo_username_collision_rolls_back(self):
        CustomUser.objects.create_user("joblyfy_sample_labs", password="real-password")
        with (
            override_settings(DEBUG=True),
            patch(
                "apps.accounts.management.commands.backup_database.Command.handle",
                return_value=None,
            ),
            self.assertRaises(CommandError),
        ):
            call_command("seed_demo", stdout=StringIO())
        self.assertFalse(Employer.objects.filter(is_demo=True).exists())
        self.assertFalse(Job.objects.filter(is_demo=True).exists())

    def test_suggestions_and_listing_queries_are_bounded(self):
        for i in range(25):
            self.add_job(title=f"Role {i}")
        with CaptureQueriesContext(connection) as queries:
            self.client.get(reverse("jobs:location_suggestions"))
        self.assertLessEqual(len(queries), 10)
        with CaptureQueriesContext(connection) as queries:
            self.search()
        self.assertLessEqual(len(queries), 18)
