import sqlite3
import tempfile
from pathlib import Path
from unittest import skipUnless

from django.core.management import call_command
from django.db import connection
from django.test import TestCase


@skipUnless(connection.vendor == "sqlite", "backup_db supports SQLite only")
class DatabaseBackupCommandTests(TestCase):
    def test_backup_is_valid_and_rotation_keeps_seven(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            backup_dir = Path(temp_dir)

            for _ in range(8):
                call_command("backup_db", directory=backup_dir, verbosity=0)

            backups = list(backup_dir.glob("library-*.sqlite3"))
            self.assertEqual(len(backups), 7)
            backup = sqlite3.connect(backups[0])
            try:
                self.assertEqual(backup.execute("PRAGMA integrity_check").fetchone()[0], "ok")
            finally:
                backup.close()
