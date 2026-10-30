from django.core.management.base import BaseCommand
from apps.jobs.models import Category


class Command(BaseCommand):
    help = "Create useful category names without adding any sample jobs, companies or people."

    def handle(self, *args, **options):
        names = [
            "Technology",
            "Design & Creative",
            "Marketing",
            "Finance",
            "Sales & Business",
            "Customer Support",
            "Engineering",
            "Human Resources",
        ]
        created = 0
        for name in names:
            _, new = Category.objects.get_or_create(
                name=name, defaults={"icon": "fas fa-briefcase"}
            )
            created += new
        self.stdout.write(
            self.style.SUCCESS(
                f"Added {created} categories; no job or account records created."
            )
        )
