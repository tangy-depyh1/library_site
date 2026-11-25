from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.core.exceptions import PermissionDenied
from django.test import Client, TestCase, override_settings
from django.urls import include, path, reverse

from project import urls as project_urls

from .models import Book, Genre, Reader, Reservation, Staff


def _raise_test_server_error(request):
    raise RuntimeError("internal test detail must not be shown")


def _raise_test_permission_denied(request):
    raise PermissionDenied


urlpatterns = [
    path("__task16_test__/403/", _raise_test_permission_denied),
    path("__task16_test__/500/", _raise_test_server_error),
    path("", include("project.urls")),
]
handler403 = project_urls.handler403
handler404 = project_urls.handler404
handler500 = project_urls.handler500


@override_settings(DEBUG=False)
class Task16ExceptionTests(TestCase):
    def create_staff(self):
        user = get_user_model().objects.create_user(
            username="task16_librarian",
            password="test-password",
        )
        Staff.objects.create(
            user=user,
            full_name="Тестовый библиотекарь",
            role=Staff.Role.LIBRARIAN,
        )
        self.client.force_login(user)
        return user

    def create_reader(self):
        user = get_user_model().objects.create_user(
            username="task16_reader",
            password="test-password",
        )
        reader = Reader.objects.create(
            user=user,
            card_number="160001",
            full_name="Тестовый читатель",
            phone="+7 900 123-45-67",
        )
        self.client.force_login(user)
        return user, reader

    def test_missing_book_uses_logged_custom_404(self):
        with self.assertLogs("library.error_views", level="WARNING") as captured:
            response = self.client.get(reverse("book_detail", args=(999999,)))

        self.assertEqual(response.status_code, 404)
        self.assertContains(response, "Страница не найдена", status_code=404)
        self.assertContains(response, 'href="/"', status_code=404)
        self.assertContains(response, 'href="/search/"', status_code=404)
        self.assertIn("HTTP 404", captured.output[0])

    def test_reader_without_staff_role_gets_logged_custom_403(self):
        user = get_user_model().objects.create_user(
            username="task16_reader_only",
            password="test-password",
        )
        Reader.objects.create(
            user=user,
            card_number="160002",
            full_name="Читатель без роли сотрудника",
        )
        self.client.force_login(user)

        with self.assertLogs("library.error_views", level="WARNING") as captured:
            response = self.client.get(reverse("staff_dashboard"))

        self.assertEqual(response.status_code, 403)
        self.assertContains(response, "Доступ запрещён", status_code=403)
        self.assertIn("HTTP 403", captured.output[0])

    def test_invalid_reader_form_keeps_values_and_does_not_create_reader(self):
        self.create_staff()
        before = Reader.objects.count()

        response = self.client.post(
            reverse("staff_reader_create"),
            {
                "card_number": "12",
                "full_name": "Проверочный читатель",
                "group_name": "ИС-16",
                "phone": "",
                "email": "",
            },
        )

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Нужно ровно 6 цифр.")
        self.assertContains(response, "Введите ровно 6 цифр без пробелов.")
        self.assertEqual(response.context["form"]["full_name"].value(), "Проверочный читатель")
        self.assertEqual(Reader.objects.count(), before)

    def test_profile_phone_validation_keeps_value_and_does_not_save(self):
        _, reader = self.create_reader()

        response = self.client.post(
            reverse("profile"),
            {"phone": "не телефон", "email": "reader@example.test"},
        )

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Введите телефон в формате +7 900 123-45-67.")
        self.assertContains(response, "Формат: +7 900 123-45-67")
        self.assertEqual(response.context["form"]["phone"].value(), "не телефон")
        reader.refresh_from_db()
        self.assertEqual(reader.phone, "+7 900 123-45-67")

    def test_reversed_report_dates_show_inline_error_and_keep_values(self):
        self.create_staff()

        response = self.client.get(
            reverse("reader_workflow_report"),
            {"start_date": "2026-02-02", "end_date": "2026-02-01"},
        )

        self.assertEqual(response.status_code, 200)
        self.assertContains(
            response,
            "Дата окончания не может быть раньше даты начала. Укажите корректный период.",
        )
        self.assertEqual(response.context["form"]["start_date"].value(), "2026-02-02")
        self.assertEqual(response.context["form"]["end_date"].value(), "2026-02-01")
        self.assertIn("end_date", response.context["form"].errors)

    def test_reservation_failure_rolls_back_partial_write_and_returns_generic_500(self):
        user, reader = self.create_reader()
        genre = Genre.objects.create(name="Тестовый жанр для исключений")
        book = Book.objects.create(
            title="Книга для проверки отката",
            genre=genre,
            year_published=2020,
        )
        reservation_manager = Reservation.objects
        create_reservation = reservation_manager.create

        def create_then_fail(*args, **kwargs):
            create_reservation(*args, **kwargs)
            raise RuntimeError("internal test detail must not be shown")

        client = Client(raise_request_exception=False)
        client.force_login(user)

        with patch.object(reservation_manager, "create", side_effect=create_then_fail):
            with self.assertLogs("library.error_views", level="ERROR") as captured:
                response = client.post(reverse("reserve", args=(book.pk,)))

        self.assertEqual(response.status_code, 500)
        self.assertContains(response, "Произошла внутренняя ошибка", status_code=500)
        self.assertNotContains(response, "internal test detail", status_code=500)
        self.assertEqual(Reservation.objects.filter(reader=reader, book=book).count(), 0)
        self.assertIn("HTTP 500", captured.output[0])

    def test_empty_overdue_report_returns_zero_totals_without_error(self):
        self.create_staff()

        response = self.client.get(
            reverse("reader_workflow_report"),
            {"start_date": "2026-01-01", "end_date": "2026-01-31"},
        )

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Просроченных выдач за период нет.")
        self.assertContains(response, "Штрафов в выбранном периоде нет.")
        self.assertEqual(response.context["overdue_count"], 0)
        self.assertEqual(response.context["fine_totals"]["all"], 0)
