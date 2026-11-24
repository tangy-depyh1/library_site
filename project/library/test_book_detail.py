from django.test import TestCase
from django.urls import reverse

from .models import Author, Book, BookAuthor, Copy, Genre


class BookDetailTests(TestCase):
    def test_isbn_is_displayed_without_hyphens(self):
        genre = Genre.objects.create(name="Роман")
        author = Author.objects.create(last_name="Толстой", first_name="Лев")
        book = Book.objects.create(
            title="Война и мир",
            genre=genre,
            isbn="978-5-14345-581-8",
            year_published=2012,
        )
        BookAuthor.objects.create(book=book, author=author)
        Copy.objects.create(book=book, inventory_number="000001")

        response = self.client.get(reverse("book_detail", args=[book.pk]))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "<dd>9785143455818</dd>", html=True)
        self.assertNotContains(response, "978-5-14345-581-8")
