from datetime import timedelta
from django.core.management.base import BaseCommand, CommandError
from django.db import transaction
from django.utils import timezone
from apps.jobs.models import ApplicationDraft


class Command(BaseCommand):
    help = "Preview unfinished applications older than 30 days; --apply removes them and their private draft resumes."

    def add_arguments(self, parser):
        parser.add_argument("--days", type=int, default=30)
        parser.add_argument("--apply", action="store_true")

    def handle(self, *args, **options):
        if options["days"] < 1:
            raise CommandError("--days must be at least 1.")
        cutoff = timezone.now() - timedelta(days=options["days"])
        ids = ApplicationDraft.objects.filter(updated_at__lt=cutoff).values_list(
            "pk", flat=True
        )
        if not options["apply"]:
            self.stdout.write(
                f"Dry run: {ids.count()} unfinished applications older than {options['days']} days. Use --apply to remove them."
            )
            return
        removed = 0
        for pk in list(ids):
            with transaction.atomic():
                draft = ApplicationDraft.objects.filter(
                    pk=pk, updated_at__lt=cutoff
                ).first()
                if draft:
                    field, name = draft.resume, draft.resume.name
                    draft.delete()
                    if name:
                        transaction.on_commit(
                            lambda field=field, name=name: field.storage.delete(name)
                        )
                    removed += 1
        self.stdout.write(
            self.style.SUCCESS(
                f"Removed {removed} unfinished applications. Submitted applications were not changed."
            )
        )
