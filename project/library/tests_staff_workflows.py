from datetime import date
from decimal import Decimal
from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse

from .models import (
    Book,
    Copy,
    Fine,
    Genre,
    LibrarySettings,
    Loan,
    Reader,
    Reservation,
    Staff,
)


class StaffWorkflowTests(TestCase):
    def setUp(self):
        user_model = get_user_model()
        self.user = user_model.objects.create_user(username="librarian", password="test-pass")
        self.staff = Staff.objects.create(
            user=self.user, full_name="Тестовый библиотекарь", role=Staff.Role.LIBRARIAN
        )
        self.client.force_login(self.user)
        self.genre = Genre.objects.create(name="Тестовый жанр")
        self.book = Book.objects.create(
            title="Тестовая книга",
            genre=self.genre,
            year_published=2020,
        )

    def create_reader(self, card_number="123456", **kwargs):
        return Reader.objects.create(
            card_number=card_number,
            full_name=kwargs.pop("full_name", "Иванов Иван Иванович"),
            **kwargs,
        )

    def create_copy(self, inventory_number="654321"):
        return Copy.objects.create(book=self.book, inventory_number=inventory_number)

    def test_staff_routes_deny_users_without_librarian_role(self):
        self.staff.role = Staff.Role.ADMIN
        self.staff.save(update_fields=["role"])

        response = self.client.get(reverse("staff_dashboard"))

        self.assertEqual(response.status_code, 403)

    def test_reader_search_and_registration(self):
        reader = self.create_reader()

        response = self.client.get(reverse("staff_readers"), {"q": reader.card_number})
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, reader.full_name)

        response = self.client.post(
            reverse("staff_reader_create"),
            {
                "card_number": "234567",
                "full_name": "Петров Пётр Петрович",
                "group_name": "ИС-21",
                "phone": "",
                "email": "",
            },
        )
        self.assertRedirects(response, reverse("staff_readers"))
        self.assertTrue(Reader.objects.filter(card_number="234567").exists())

    def test_issue_rejects_blocked_reader_and_non_stock_copy(self):
        blocked_reader = self.create_reader(is_blocked=True, block_reason="Неоплаченный штраф")
        copy = self.create_copy()
        response = self.client.post(
            reverse("staff_issue"),
            {"card_number": blocked_reader.card_number, "inventory_number": copy.inventory_number},
        )
        self.assertEqual(response.status_code, 200)
        self.assertFalse(Loan.objects.exists())

        blocked_reader.is_blocked = False
        blocked_reader.block_reason = ""
        blocked_reader.save(update_fields=["is_blocked", "block_reason"])
        copy.status = Copy.Status.RESERVED
        copy.save(update_fields=["status"])
        response = self.client.post(
            reverse("staff_issue"),
            {"card_number": blocked_reader.card_number, "inventory_number": copy.inventory_number},
        )
        self.assertEqual(response.status_code, 200)
        self.assertFalse(Loan.objects.exists())

    def test_issue_uses_configured_loan_period(self):
        reader = self.create_reader()
        copy = self.create_copy()
        settings = LibrarySettings.get()
        settings.loan_days = 7
        settings.save()

        with patch("library.staff_views.timezone.localdate", return_value=date(2026, 1, 1)):
            response = self.client.post(
                reverse("staff_issue"),
                {"card_number": reader.card_number, "inventory_number": copy.inventory_number},
            )

        self.assertRedirects(response, reverse("staff_issue"))
        loan = Loan.objects.get()
        self.assertEqual(loan.due_date, date(2026, 1, 8))
        copy.refresh_from_db()
        self.assertEqual(copy.status, Copy.Status.ON_LOAN)

    def test_issue_default_period_matches_tc50(self):
        reader = self.create_reader()
        copy = self.create_copy("100002")
        LibrarySettings.get()

        with patch("library.staff_views.timezone.localdate", return_value=date(2026, 11, 13)):
            response = self.client.post(
                reverse("staff_issue"),
                {
                    "card_number": reader.card_number,
                    "inventory_number": copy.inventory_number,
                },
            )

        self.assertRedirects(response, reverse("staff_issue"))
        loan = Loan.objects.get()
        self.assertEqual(loan.due_date, date(2026, 11, 27))
        copy.refresh_from_db()
        self.assertEqual(copy.status, Copy.Status.ON_LOAN)

    def test_on_time_return_matches_tc54(self):
        reader = self.create_reader()
        copy = self.create_copy("100194")
        copy.status = Copy.Status.ON_LOAN
        copy.save(update_fields=["status"])
        loan = Loan.objects.create(
            copy=copy,
            reader=reader,
            issued_by=self.staff,
            issued_at=date(2026, 11, 1),
            due_date=date(2026, 11, 13),
        )

        with patch("library.staff_views.timezone.localdate", return_value=date(2026, 11, 13)):
            response = self.client.post(
                reverse("staff_return"),
                {
                    "inventory_number": copy.inventory_number,
                    "condition": Copy.Condition.GOOD,
                },
            )

        self.assertRedirects(response, reverse("staff_return"))
        loan.refresh_from_db()
        copy.refresh_from_db()
        self.assertEqual(loan.returned_at, date(2026, 11, 13))
        self.assertEqual(copy.status, Copy.Status.IN_STOCK)
        self.assertFalse(Fine.objects.filter(loan=loan).exists())

    def test_return_assigns_queue_reservation_and_issue_fulfills_it(self):
        reader = self.create_reader()
        copy = self.create_copy()
        copy.status = Copy.Status.ON_LOAN
        copy.save(update_fields=["status"])
        loan = Loan.objects.create(
            copy=copy,
            reader=reader,
            issued_by=self.staff,
            issued_at=date(2026, 1, 1),
            due_date=date(2026, 1, 1),
        )
        waiting_reader = self.create_reader(
            card_number="234567",
            full_name="Петров Пётр Петрович",
        )
        reservation = Reservation.objects.create(reader=waiting_reader, book=self.book)

        with patch("library.staff_views.timezone.localdate", return_value=date(2026, 1, 1)):
            response = self.client.post(
                reverse("staff_return"),
                {
                    "inventory_number": copy.inventory_number,
                    "condition": Copy.Condition.GOOD,
                },
            )
        self.assertRedirects(response, reverse("staff_return"))
        reservation.refresh_from_db()
        copy.refresh_from_db()
        loan.refresh_from_db()
        self.assertEqual(reservation.status, "ready")
        self.assertEqual(reservation.assigned_copy, copy)
        self.assertEqual(copy.status, Copy.Status.RESERVED)
        self.assertEqual(loan.returned_at, date(2026, 1, 1))
        with patch("library.staff_views.timezone.localdate", return_value=date(2026, 1, 1)):
            queue_response = self.client.get(reverse("staff_reservations"))
        self.assertContains(queue_response, waiting_reader.full_name)
        self.assertContains(queue_response, "Выдать по заявке")

        response = self.client.post(
            reverse("staff_issue"),
            {
                "card_number": waiting_reader.card_number,
                "inventory_number": copy.inventory_number,
            },
        )
        self.assertRedirects(response, reverse("staff_issue"))
        reservation.refresh_from_db()
        copy.refresh_from_db()
        issued_loan = Loan.objects.get(reservation=reservation)
        self.assertEqual(reservation.status, "fulfilled")
        self.assertEqual(issued_loan.reader, waiting_reader)
        self.assertEqual(copy.status, Copy.Status.ON_LOAN)

    def test_overdue_return_creates_fine_and_payment_clears_workflow_block(self):
        reader = self.create_reader()
        copy = self.create_copy()
        settings = LibrarySettings.get()
        settings.loan_days = 1
        settings.fine_per_day = Decimal("2.50")
        settings.save()

        with patch("library.staff_views.timezone.localdate", return_value=date(2026, 1, 1)):
            self.client.post(
                reverse("staff_issue"),
                {"card_number": reader.card_number, "inventory_number": copy.inventory_number},
            )
        with patch("library.staff_views.timezone.localdate", return_value=date(2026, 1, 5)):
            response = self.client.post(
                reverse("staff_return"),
                {
                    "inventory_number": copy.inventory_number,
                    "condition": Copy.Condition.WORN,
                },
            )

        self.assertRedirects(response, reverse("staff_return"))
        loan = Loan.objects.get()
        fine = Fine.objects.get(loan=loan)
        self.assertEqual(fine.days_overdue, 3)
        self.assertEqual(fine.amount, Decimal("7.50"))
        reader.refresh_from_db()
        self.assertTrue(reader.is_blocked)
        copy.refresh_from_db()
        self.assertEqual(copy.status, Copy.Status.IN_STOCK)
        self.assertEqual(copy.condition, Copy.Condition.WORN)

        response = self.client.post(reverse("staff_fine_pay", args=[fine.pk]))
        self.assertRedirects(response, reverse("staff_fines"))
        fine.refresh_from_db()
        reader.refresh_from_db()
        self.assertEqual(fine.status, Fine.Status.PAID)
        self.assertFalse(reader.is_blocked)

    def test_settings_can_be_updated(self):
        self.staff.role = Staff.Role.ADMIN
        self.staff.save(update_fields=["role"])
        LibrarySettings.get()
        self.assertEqual(self.client.get(reverse("admin_settings")).status_code, 200)

        response = self.client.post(
            reverse("staff_settings"),
            {
                "fine_per_day": "8.00",
                "loan_days": "21",
                "renewal_days": "14",
                "max_renewals": "1",
                "reservation_hold_days": "3",
                "reminder_days": "2",
            },
        )

        self.assertRedirects(response, reverse("staff_settings"))
        self.assertEqual(LibrarySettings.get().fine_per_day, Decimal("8.00"))

    def test_staff_settings_are_admin_only_and_admin_can_create_staff_account(self):
        self.assertEqual(
            self.client.get(reverse("staff_settings")).status_code,
            403,
        )
        self.staff.role = Staff.Role.ADMIN
        self.staff.save(update_fields=["role"])
        self.assertEqual(self.client.get(reverse("staff_accounts")).status_code, 200)

        response = self.client.post(
            reverse("staff_accounts"),
            {
                "username": "new_librarian",
                "password1": "StrongTestPass123!",
                "password2": "StrongTestPass123!",
                "full_name": "Новый библиотекарь",
                "role": Staff.Role.LIBRARIAN,
                "position": "Библиотекарь",
            },
        )

        self.assertRedirects(response, reverse("staff_accounts"))
        self.assertTrue(
            Staff.objects.filter(
                user__username="new_librarian",
                role=Staff.Role.LIBRARIAN,
            ).exists()
        )

    def test_issue_rejects_unflagged_reader_with_open_overdue_loan(self):
        reader = self.create_reader()
        overdue_copy = self.create_copy("654322")
        overdue_copy.status = Copy.Status.ON_LOAN
        overdue_copy.save(update_fields=["status"])
        Loan.objects.create(
            copy=overdue_copy,
            reader=reader,
            issued_by=self.staff,
            issued_at=date(2026, 1, 1),
            due_date=date(2026, 1, 2),
        )
        available_copy = self.create_copy("654323")

        with patch("library.staff_views.timezone.localdate", return_value=date(2026, 1, 3)):
            response = self.client.post(
                reverse("staff_issue"),
                {
                    "card_number": reader.card_number,
                    "inventory_number": available_copy.inventory_number,
                },
            )

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "просроченная выдача")
        self.assertEqual(Loan.objects.count(), 1)

    def test_issue_shows_amount_for_unpaid_fine_even_without_block_flag(self):
        reader = self.create_reader()
        returned_copy = self.create_copy("654322")
        returned_loan = Loan.objects.create(
            copy=returned_copy,
            reader=reader,
            issued_by=self.staff,
            issued_at=date(2026, 1, 1),
            due_date=date(2026, 1, 2),
            returned_at=date(2026, 1, 3),
            return_condition=Copy.Condition.GOOD,
        )
        Fine.objects.create(
            loan=returned_loan,
            days_overdue=1,
            rate_per_day=Decimal("105.00"),
            amount=Decimal("105.00"),
        )
        available_copy = self.create_copy("654323")

        with patch("library.staff_views.timezone.localdate", return_value=date(2026, 1, 3)):
            response = self.client.post(
                reverse("staff_issue"),
                {
                    "card_number": reader.card_number,
                    "inventory_number": available_copy.inventory_number,
                },
            )

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Не оплачен штраф: 105 руб.")
        self.assertEqual(Loan.objects.count(), 1)
