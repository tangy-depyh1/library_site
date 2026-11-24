import sqlite3
from pathlib import Path

from django.conf import settings
from django.core.management.base import BaseCommand, CommandError
from django.db import connection
from django.utils import timezone


class Command(BaseCommand):
    help = "Create an SQLite database backup; schedule this command to run daily."

    def add_arguments(self, parser):
        parser.add_argument(
            "--directory",
            type=Path,
            default=settings.BASE_DIR / "backups",
            help="Directory for backup files (default: %(default)s)",
        )

    def handle(self, *args, **options):
        if connection.vendor != "sqlite":
            raise CommandError("backup_db currently supports SQLite only.")

        backup_dir = options["directory"]
        backup_dir.mkdir(parents=True, exist_ok=True)
        timestamp = timezone.localtime().strftime("%Y%m%d-%H%M%S-%f")
        backup_path = backup_dir / f"library-{timestamp}.sqlite3"

        connection.ensure_connection()
        destination = sqlite3.connect(backup_path)
        try:
            connection.connection.backup(destination)
        finally:
            destination.close()

        backups = sorted(
            backup_dir.glob("library-*.sqlite3"),
            key=lambda path: (path.stat().st_mtime_ns, path.name),
            reverse=True,
        )
        for old_backup in backups[7:]:
            old_backup.unlink()

        self.stdout.write(self.style.SUCCESS(f"Database backup created: {backup_path}"))
