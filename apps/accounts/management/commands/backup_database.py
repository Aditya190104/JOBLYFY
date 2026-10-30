from pathlib import Path
import sqlite3
from datetime import datetime, timezone
from django.conf import settings
from django.core.management.base import BaseCommand, CommandError


class Command(BaseCommand):
    help = "Create a consistent SQLite backup without modifying the source database."

    def handle(self, *args, **options):
        path = Path(settings.DATABASES["default"]["NAME"])
        if not path.exists():
            raise CommandError("No database exists yet. Run migrate to create one.")
        directory = settings.BASE_DIR / "backups"
        directory.mkdir(exist_ok=True)
        target = directory / (
            "db-" + datetime.now(timezone.utc).strftime("%Y%m%d-%H%M%S-%f") + ".sqlite3"
        )
        with (
            sqlite3.connect(f"file:{path.as_posix()}?mode=ro", uri=True) as source,
            sqlite3.connect(target) as dest,
        ):
            source.backup(dest)
        self.stdout.write(self.style.SUCCESS("Backup created: " + str(target)))
