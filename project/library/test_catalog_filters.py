from django.test import TestCase
from django.urls import reverse

from .models import Author, Book, BookAuthor, Copy, Genre


class CatalogAuthorFilterTests(TestCase):
    def setUp(self):
        self.genre = Genre.objects.create(name="Роман")
        self.author = Author.objects.create(last_name="Толстой", first_name="Лев")
        self.coauthor = Author.objects.create(last_name="Иванов", first_name="Иван")
        self.other_author = Author.objects.create(last_name="Петров", first_name="Пётр")

        self.match = Book.objects.create(
            title="Книга с двумя авторами",
            genre=self.genre,
            year_published=2020,
        )
        BookAuthor.objects.create(book=self.match, author=self.author, position=1)
        BookAuthor.objects.create(book=self.match, author=self.coauthor, position=2)
        Copy.objects.create(book=self.match, inventory_number="000001")
        Copy.objects.create(book=self.match, inventory_number="000002")

        self.other = Book.objects.create(
            title="Другая книга",
            genre=self.genre,
            year_published=2020,
        )
        BookAuthor.objects.create(book=self.other, author=self.other_author, position=1)
        Copy.objects.create(book=self.other, inventory_number="000003")

    def test_author_filter_returns_only_matching_books_without_duplicate_copies(self):
        response = self.client.get(reverse("catalog"), {"author": self.author.pk})

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.context["page"].paginator.count, 1)
        self.assertContains(response, self.match.title)
        self.assertNotContains(response, self.other.title)
        self.assertContains(response, "Свободно 2 из 2")

    def test_author_filter_combines_with_genre_and_free_filters(self):
        response = self.client.get(
            reverse("catalog"),
            {"author": self.author.pk, "genre": self.genre.pk, "free": "1"},
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.context["page"].paginator.count, 1)
