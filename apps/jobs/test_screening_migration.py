from django.db import connection
from django.db.migrations.executor import MigrationExecutor
from django.test import TransactionTestCase


class ScreeningMigrationTests(TransactionTestCase):
    def test_existing_data_survives_forward_migration(self):
        before = ("jobs", "0004_companyreview_job_demo_key_job_is_demo_and_more")
        after = ("jobs", "0005_job_screening_workflow")
        executor = MigrationExecutor(connection)
        executor.migrate([before])
        apps = executor.loader.project_state([before]).apps
        User, Employer, Seeker = [
            apps.get_model("accounts", n)
            for n in ("CustomUser", "Employer", "JobSeeker")
        ]
        Job, Application = [apps.get_model("jobs", n) for n in ("Job", "Application")]
        user = User.objects.create(
            username="migration-employer", password="preserved-hash", is_employer=True
        )
        candidate = User.objects.create(
            username="migration-candidate",
            password="preserved-candidate-hash",
            is_job_seeker=True,
        )
        employer = Employer.objects.create(user=user, company_name="Migration fixture")
        seeker = Seeker.objects.create(user=candidate, education="Original education")
        active = Job.objects.create(
            title="Existing role",
            employer=employer,
            description="Original description",
            requirements="Original requirements",
            location="Mohali",
            job_type="full_time",
            salary="Original salary",
            is_active=True,
        )
        paused = Job.objects.create(
            title="Inactive role",
            employer=employer,
            description="Keep me",
            requirements="Keep requirements",
            location="Delhi",
            job_type="full_time",
            is_active=False,
        )
        application = Application.objects.create(
            job=active,
            job_seeker=seeker,
            cover_letter="Original cover letter",
            status="shortlisted",
            resume="application_resumes/existing.pdf",
        )
        try:
            executor = MigrationExecutor(connection)
            executor.migrate([after])
            apps = executor.loader.project_state([after]).apps
            upgraded = apps.get_model("jobs", "Job").objects.get(pk=active.pk)
            self.assertEqual(
                (upgraded.publication_status, upgraded.is_active), ("published", True)
            )
            self.assertEqual(upgraded.description, "Original description")
            self.assertEqual(upgraded.requirements, "Original requirements")
            self.assertEqual(upgraded.salary, "Original salary")
            self.assertEqual(upgraded.employer_id, employer.pk)
            upgraded = apps.get_model("jobs", "Job").objects.get(pk=paused.pk)
            self.assertEqual(
                (upgraded.publication_status, upgraded.is_active), ("paused", False)
            )
            app = apps.get_model("jobs", "Application").objects.get(pk=application.pk)
            self.assertEqual(app.status, "shortlisted")
            self.assertEqual(app.cover_letter, "Original cover letter")
            self.assertEqual(app.resume.name, "application_resumes/existing.pdf")
            self.assertEqual(app.screening_outcome, "legacy")
            self.assertEqual(app.eligibility_snapshot, {})
            self.assertEqual(app.candidate_snapshot, {})
            self.assertEqual(
                apps.get_model("jobs", "EligibilityRule").objects.count(), 0
            )
            self.assertEqual(
                apps.get_model("accounts", "CustomUser")
                .objects.get(pk=user.pk)
                .password,
                "preserved-hash",
            )
        finally:
            executor = MigrationExecutor(connection)
            executor.migrate(executor.loader.graph.leaf_nodes())
