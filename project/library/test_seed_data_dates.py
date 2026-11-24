from datetime import date

from django.core.management import call_command
from django.test import TestCase

from .models import Book
from .seed_logic import build


class SeedDataDateTests(TestCase):
    def test_book_creation_dates_use_the_requested_seed_date(self):
        today = date(2026, 11, 13)
        expected, _ = build(today, books=18, readers=1, seed=42)

        call_command("seed_data", today=today, books=18, readers=1, seed=42, verbosity=0)

        self.assertEqual(
            Book.objects.get(pk=1).created_at.date(),
            expected["book"][0]["created_at"].date(),
        )
