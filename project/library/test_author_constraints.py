from django.db import IntegrityError, transaction
from django.test import TestCase

from .models import Author


class AuthorUniquenessTests(TestCase):
    def test_authors_without_birth_year_are_unique(self):
        Author.objects.create(
            last_name="Иванов",
            first_name="Иван",
            middle_name="Иванович",
            birth_year=None,
        )

        with self.assertRaises(IntegrityError):
            with transaction.atomic():
                Author.objects.create(
                    last_name="Иванов",
                    first_name="Иван",
                    middle_name="Иванович",
                    birth_year=None,
                )
