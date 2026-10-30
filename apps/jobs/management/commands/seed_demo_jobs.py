"""Backup-first, transactional career fixtures for local practice workflows."""

from datetime import timedelta
from decimal import Decimal
from django.conf import settings
from django.core.management import call_command
from django.core.management.base import BaseCommand, CommandError
from django.db import transaction
from django.db.models import F
from django.utils import timezone
from apps.accounts.models import CustomUser, Employer
from apps.jobs.demo_catalog import COMPANIES, JOBS, DEMO_PREFIX
from apps.jobs.models import Category, Job, EligibilityRule, ScreeningQuestion


def save_validated(instance):
    instance.full_clean()
    instance.save()
    return instance


class Command(BaseCommand):
    help = "Create 18 fictional software/design jobs with screening in DEBUG mode. Existing data is preserved."

    def add_arguments(self, parser):
        actions = parser.add_mutually_exclusive_group()
        actions.add_argument(
            "--deactivate",
            action="store_true",
            help="Pause catalog jobs, preserving all records.",
        )
        actions.add_argument(
            "--reactivate",
            action="store_true",
            help="Publish existing catalog jobs and renew deadlines.",
        )
        actions.add_argument(
            "--remove-unused",
            action="store_true",
            help="Delete only catalog jobs without applications, drafts or saved-job references; retain accounts/categories.",
        )
        parser.add_argument(
            "--refresh-deadlines",
            action="store_true",
            help="Seed missing entries and renew existing deadlines for 60 days without unpausing jobs.",
        )

    def handle(self, *args, **options):
        if not settings.DEBUG:
            raise CommandError(
                "Demo jobs are local-development features (DJANGO_DEBUG=True). Do not enable DEBUG on a public deployment."
            )
        if options["refresh_deadlines"] and any(
            options[k] for k in ("deactivate", "reactivate", "remove_unused")
        ):
            raise CommandError(
                "Use --refresh-deadlines with normal seeding or choose one lifecycle action."
            )
        keys = [DEMO_PREFIX + row["slug"] for row in JOBS]
        if len(set(keys)) != len(keys):
            raise CommandError("Catalog slugs must be unique. No records changed.")
        call_command("backup_database", stdout=self.stdout)
        with transaction.atomic():
            teams = {}
            for key, values in COMPANIES.items():
                user = CustomUser.objects.filter(username=values["username"]).first()
                if user:
                    team = Employer.objects.filter(user=user, is_demo=True).first()
                    if not team or not user.is_employer or user.is_job_seeker:
                        raise CommandError(
                            "Reserved demo username belongs to an unrelated account. Transaction rolled back."
                        )
                    teams[key] = team
            existing = {
                j.demo_key: j
                for j in Job.objects.filter(demo_key__in=keys).select_related(
                    "employer__user"
                )
            }
            for row in JOBS:
                job, expected = (
                    existing.get(DEMO_PREFIX + row["slug"]),
                    teams.get(row["company"]),
                )
                if job and (
                    not job.is_demo or not expected or job.employer_id != expected.pk
                ):
                    raise CommandError(
                        "Catalog identifier belongs to an unrelated job. Transaction rolled back."
                    )
            owned = Job.objects.filter(pk__in=[j.pk for j in existing.values()])
            deadline = timezone.localdate() + timedelta(days=60)
            if options["deactivate"]:
                count = owned.update(
                    is_active=False,
                    publication_status="paused",
                    screening_revision=F("screening_revision") + 1,
                )
                self.stdout.write(f"Paused {count} demo jobs; all records retained.")
                return
            if options["reactivate"]:
                count = owned.update(
                    is_active=True,
                    publication_status="published",
                    deadline=deadline,
                    screening_revision=F("screening_revision") + 1,
                )
                self.stdout.write(
                    f"Published {count} demo jobs; deadlines renewed to {deadline}."
                )
                return
            if options["remove_unused"]:
                unused = owned.filter(
                    applications__isnull=True,
                    application_drafts__isnull=True,
                    saves__isnull=True,
                )
                count, retained = unused.count(), owned.count() - unused.count()
                unused.delete()
                self.stdout.write(
                    f"Removed {count} unused demo jobs; retained {retained} referenced jobs. Accounts and categories retained."
                )
                return
            for key, values in COMPANIES.items():
                if key not in teams:
                    user = CustomUser(
                        username=values["username"], is_employer=True, email=""
                    )
                    user.set_unusable_password()
                    user.save()
                    teams[key] = save_validated(
                        Employer(
                            user=user,
                            is_demo=True,
                            **{k: v for k, v in values.items() if k != "username"},
                        )
                    )
            created = 0
            for row in JOBS:
                key = DEMO_PREFIX + row["slug"]
                if key in existing:
                    continue
                category = (
                    Category.objects.filter(name=row["category"]).order_by("pk").first()
                )
                if category is None:
                    category = save_validated(
                        Category(name=row["category"], icon="fas fa-briefcase")
                    )
                low, high = row["salary"]
                factor = 12 if row["monthly"] else 1
                job = save_validated(
                    Job(
                        title=row["title"],
                        employer=teams[row["company"]],
                        category=category,
                        description="DEVELOPMENT SAMPLE — fictional vacancy, company and compensation. Practice applications only.\n\n"
                        + row["description"],
                        responsibilities=row["responsibilities"],
                        qualifications=row["qualifications"],
                        requirements=row["requirements"],
                        mandatory_skills=", ".join(row["mandatory"]),
                        preferred_skills=", ".join(row["preferred"]),
                        min_experience=Decimal(str(row["experience"][0])),
                        max_experience=Decimal(str(row["experience"][1])),
                        salary_min=low * factor,
                        salary_max=high * factor,
                        salary=f"₹{low:,}–₹{high:,} per month (sample stipend)"
                        if row["monthly"]
                        else f"₹{low / 100000:g}–₹{high / 100000:g} LPA (illustrative)",
                        location=row["location"],
                        work_mode=row["work_mode"],
                        job_type=row["job_type"],
                        experience_level=row["experience_level"],
                        benefits=row["benefits"],
                        deadline=deadline,
                        is_active=True,
                        publication_status="published",
                        is_demo=True,
                        demo_key=key,
                        is_featured=row["featured"],
                        application_instructions="Local practice only: review the saved criteria, answer required questions, select a PDF and review before submitting. Use a test resume without private or employer-confidential information. Your record is visible only to you and this demo company's authorized recruiter. No real employer receives it.",
                    )
                )
                rules = [
                    dict(
                        kind="qualification", values=row["accepted"], is_blocking=True
                    ),
                    dict(kind="experience", is_blocking=True),
                    dict(kind="skills", is_blocking=True),
                    dict(kind="work_arrangement", is_blocking=True),
                ]
                if row["work_mode"] != "remote":
                    rules.append(
                        dict(
                            kind="location",
                            values=[row["location"]],
                            allow_relocation=True,
                            is_blocking=True,
                        )
                    )
                for rule in rules:
                    save_validated(EligibilityRule(job=job, **rule))
                questions = [
                    dict(
                        prompt="Do you understand that this is a fictional practice vacancy and not a real employer application?",
                        kind="yes_no",
                        match_mode="any",
                        expected_answers=["yes"],
                        is_blocking=True,
                    ),
                    dict(
                        prompt="When could you start if this were a suitable real opportunity?",
                        kind="single",
                        options=[
                            "Within 2 weeks",
                            "Within 1 month",
                            "More than 1 month",
                        ],
                    ),
                    dict(
                        prompt="Which of these tools or skills have you used in coursework, projects or work?",
                        kind="multiple",
                        options=row["mandatory"] + row["preferred"],
                        match_mode="any",
                        expected_answers=row["mandatory"],
                    ),
                    dict(prompt=row["project_prompt"], kind="text"),
                ]
                for position, question in enumerate(questions, 1):
                    save_validated(
                        ScreeningQuestion(
                            job=job, position=position, required=True, **question
                        )
                    )
                created += 1
            if options["refresh_deadlines"]:
                owned.update(
                    deadline=deadline, screening_revision=F("screening_revision") + 1
                )
            catalog = Job.objects.filter(demo_key__in=keys, is_demo=True)
            self.stdout.write(
                f"Created {created} demo jobs; {len(existing)} existing catalog jobs preserved. {catalog.open().count()} of {catalog.count()} catalog jobs are open."
            )
            self.stdout.write(
                "Practice applications are local only. No applications or reviews were fabricated. Set a private password with manage.py changepassword USERNAME to review as a demo recruiter."
            )
            self.stdout.write(
                "Demo usernames: "
                + ", ".join(v["username"] for v in COMPANIES.values())
            )
            self.stdout.write(
                "Paused/expired records remain unchanged unless --refresh-deadlines or --reactivate is explicitly requested."
            )
