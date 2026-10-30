"""Explicit, development-only fictional data. Never overwrites a real account or job."""

from datetime import timedelta
from django.conf import settings
from django.core.management import call_command
from django.core.management.base import BaseCommand, CommandError
from django.db import transaction
from django.utils import timezone
from apps.accounts.models import CustomUser, Employer
from apps.jobs.models import Category, Job


class Command(BaseCommand):
    help = "Create labelled fictional sample listings for local development only (DEBUG=True). Idempotent; no reviews or applications are fabricated."

    def add_arguments(self, parser):
        parser.add_argument(
            "--deactivate",
            action="store_true",
            help="Deactivate only this command's sample jobs; retain all records.",
        )

    def handle(self, *args, **options):
        if not settings.DEBUG:
            raise CommandError(
                "Sample data is allowed only with DJANGO_DEBUG=True. Do not enable DEBUG on a public deployment."
            )
        # Backup the selected SQLite database before adding or deactivating records.
        call_command("backup_database", stdout=self.stdout)
        with transaction.atomic():
            if options["deactivate"]:
                count = Job.objects.filter(
                    is_demo=True, demo_key__startswith="joblyfy-v1:"
                ).update(is_active=False)
                self.stdout.write(
                    self.style.SUCCESS(
                        f"Deactivated {count} sample listings. All records preserved."
                    )
                )
                return
            call_command("seed_categories", stdout=self.stdout)
            teams = []
            for key, name, industry, location in [
                (
                    "studio",
                    "Lavender Studio — Sample",
                    "Software & product design",
                    "Mohali",
                ),
                ("labs", "Northlane Labs — Sample", "Technology", "Bengaluru"),
                (
                    "works",
                    "Chapter Works — Sample",
                    "Business & creative services",
                    "Delhi",
                ),
            ]:
                username = "joblyfy_sample_" + key
                user = CustomUser.objects.filter(username=username).first()
                if user is not None:
                    employer = Employer.objects.filter(user=user, is_demo=True).first()
                    if not employer or user.has_usable_password():
                        raise CommandError(
                            f"Reserved sample username {username} belongs to a non-sample account. No records were changed."
                        )
                else:
                    user = CustomUser(username=username, email="", is_employer=True)
                    user.set_unusable_password()
                    user.save()
                    employer = Employer.objects.create(
                        user=user,
                        company_name=name,
                        industry=industry,
                        location=location,
                        is_demo=True,
                        company_description="Fictional company for the JOBLYFY local development preview. This is not a real employer. Sample listings cannot receive applications.",
                    )
                teams.append(employer)
            # Fictional example roles and pay, always identified as samples in the UI.
            rows = [
                (
                    "Frontend Developer",
                    0,
                    "Mohali",
                    "full_time",
                    "hybrid",
                    "entry",
                    "Technology",
                    450000,
                    750000,
                    "HTML CSS JavaScript React",
                ),
                (
                    "Python Developer",
                    0,
                    "Chandigarh",
                    "full_time",
                    "onsite",
                    "entry",
                    "Technology",
                    500000,
                    850000,
                    "Python Django SQL Git",
                ),
                (
                    "UI / UX Designer",
                    0,
                    "Ludhiana",
                    "full_time",
                    "hybrid",
                    "entry",
                    "Design & Creative",
                    400000,
                    650000,
                    "Figma design accessibility research",
                ),
                (
                    "Full-Stack Engineer",
                    1,
                    "Bengaluru",
                    "full_time",
                    "hybrid",
                    "mid",
                    "Technology",
                    900000,
                    1500000,
                    "React Python Django APIs SQL",
                ),
                (
                    "Remote JavaScript Developer",
                    1,
                    "Remote — India",
                    "contract",
                    "remote",
                    "mid",
                    "Technology",
                    800000,
                    1200000,
                    "JavaScript TypeScript accessibility APIs",
                ),
                (
                    "Software Engineering Intern",
                    0,
                    "Mohali",
                    "internship",
                    "onsite",
                    "entry",
                    "Technology",
                    180000,
                    300000,
                    "Python Git testing HTML CSS",
                ),
                (
                    "Digital Marketing Associate",
                    2,
                    "Delhi",
                    "full_time",
                    "onsite",
                    "entry",
                    "Marketing",
                    350000,
                    550000,
                    "SEO content analytics campaigns",
                ),
                (
                    "Customer Support Specialist",
                    2,
                    "Remote — India",
                    "part_time",
                    "remote",
                    "entry",
                    "Customer Support",
                    240000,
                    360000,
                    "communication support English",
                ),
                (
                    "Senior Backend Engineer",
                    1,
                    "Bengaluru",
                    "full_time",
                    "hybrid",
                    "senior",
                    "Technology",
                    1800000,
                    2600000,
                    "Python Django architecture PostgreSQL",
                ),
                (
                    "Product Designer",
                    0,
                    "Chandigarh",
                    "contract",
                    "hybrid",
                    "mid",
                    "Design & Creative",
                    700000,
                    1100000,
                    "Figma prototyping research design systems",
                ),
                (
                    "Business Development Associate",
                    2,
                    "Ludhiana",
                    "full_time",
                    "onsite",
                    "entry",
                    "Sales & Business",
                    350000,
                    600000,
                    "sales communication research CRM",
                ),
                (
                    "QA Automation Engineer",
                    1,
                    "Pune",
                    "full_time",
                    "hybrid",
                    "mid",
                    "Technology",
                    650000,
                    1000000,
                    "Python Playwright testing quality",
                ),
                (
                    "Finance Analyst",
                    2,
                    "Mumbai",
                    "full_time",
                    "onsite",
                    "entry",
                    "Finance",
                    500000,
                    800000,
                    "Excel accounting analysis",
                ),
                (
                    "People Operations Coordinator",
                    2,
                    "Delhi",
                    "full_time",
                    "hybrid",
                    "mid",
                    "Human Resources",
                    450000,
                    700000,
                    "recruiting communication operations",
                ),
                (
                    "Web Development Intern",
                    0,
                    "Ludhiana",
                    "internship",
                    "hybrid",
                    "entry",
                    "Technology",
                    None,
                    None,
                    "HTML CSS JavaScript Git",
                ),
                (
                    "Remote Technical Writer",
                    1,
                    "Remote — India",
                    "contract",
                    "remote",
                    "mid",
                    "Technology",
                    None,
                    None,
                    "Python documentation APIs writing",
                ),
                (
                    "React Developer",
                    1,
                    "Hyderabad",
                    "full_time",
                    "onsite",
                    "mid",
                    "Technology",
                    800000,
                    1300000,
                    "React JavaScript CSS Git",
                ),
                (
                    "Junior Data Analyst",
                    2,
                    "Chennai",
                    "full_time",
                    "hybrid",
                    "entry",
                    "Technology",
                    450000,
                    700000,
                    "SQL Python Excel analytics",
                ),
            ]
            created = 0
            for i, (
                title,
                team,
                location,
                kind,
                mode,
                level,
                category,
                low,
                high,
                skills,
            ) in enumerate(rows):
                cat = Category.objects.filter(name=category).first()
                job, is_new = Job.objects.get_or_create(
                    demo_key=f"joblyfy-v1:{i + 1}",
                    defaults={
                        "title": title,
                        "employer": teams[team],
                        "category": cat,
                        "location": location,
                        "job_type": kind,
                        "work_mode": mode,
                        "experience_level": level,
                        "salary_min": low,
                        "salary_max": high,
                        "salary": "",
                        "description": f"SAMPLE LISTING — not a real vacancy. Explore how a {title.lower()} role appears on JOBLYFY. In this fictional example, the role focuses on useful products, thoughtful collaboration and clear communication. The company, opportunity and advertised pay are demonstration data.",
                        "requirements": f"Example skills: {skills}. Curiosity, clear communication and an interest in building useful work. These are sample requirements, not a hiring invitation.",
                        "benefits": "Sample examples: flexible hours, structured mentoring and a learning budget. Not an offer from a real employer.",
                        "is_demo": True,
                        "is_featured": i < 3,
                        "deadline": timezone.localdate() + timedelta(days=45),
                    },
                )
                if not job.is_demo or job.employer_id != teams[team].pk:
                    raise CommandError(
                        "A sample identifier collides with a non-sample record. No records were changed."
                    )
                if is_new:
                    Job.objects.filter(pk=job.pk).update(
                        posted_date=timezone.now() - timedelta(days=i, hours=i)
                    )
                    created += 1
            self.stdout.write(
                self.style.SUCCESS(
                    f"Created {created} sample jobs. Existing records were not overwritten. Sample accounts have no usable password; reviews and applications were not seeded."
                )
            )
