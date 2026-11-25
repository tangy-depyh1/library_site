from datetime import timedelta
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.core.management import call_command
from django.test import TestCase, override_settings
from django.urls import reverse
from django.utils import timezone

from .models import (
    Book,
    Copy,
    Fine,
    Genre,
    LibrarySettings,
    Loan,
    Notification,
    Reader,
    Renewal,
    Reservation,
    Staff,
)
from .reader_workflow_views import urlpatterns as workflow_urlpatterns
from .urls import urlpatterns as app_urlpatterns


urlpatterns = [*app_urlpatterns, *workflow_urlpatterns]


@override_settings(ROOT_URLCONF=__name__)
class ReaderWorkflowTests(TestCase):
    def setUp(self):
        user_model = get_user_model()
        self.reader_user = user_model.objects.create_user(
            username="reader_workflow", password="test-password"
        )
        self.reader = Reader.objects.create(
            user=self.reader_user,
            card_number="100001",
            full_name="Reader One",
        )
        self.other_reader = Reader.objects.create(
            card_number="100002",
            full_name="Reader Two",
        )
        self.staff_user = user_model.objects.create_user(
            username="staff_workflow", password="test-password"
        )
        self.staff = Staff.objects.create(
            user=self.staff_user,
            full_name="Staff One",
            role=Staff.Role.LIBRARIAN,
        )
        self.genre = Genre.objects.create(name="Workflow genre")
        self.book = Book.objects.create(
            title="Workflow book",
            genre=self.genre,
            year_published=2020,
        )
        self.copy = Copy.objects.create(
            book=self.book,
            inventory_number="100001",
            status=Copy.Status.ON_LOAN,
        )
        self.today = timezone.localdate()
        self.loan = Loan.objects.create(
            copy=self.copy,
            reader=self.reader,
            issued_by=self.staff,
            issued_at=self.today - timedelta(days=7),
            due_date=self.today + timedelta(days=7),
        )

    def test_return_assigns_copy_to_oldest_reservation_and_notifies_reader(self):
        oldest = Reservation.objects.create(
            reader=self.other_reader,
            book=self.book,
            created_at=timezone.now() - timedelta(minutes=2),
        )
        newer = Reservation.objects.create(
            reader=self.reader,
            book=self.book,
            created_at=timezone.now() - timedelta(minutes=1),
        )
        self.client.force_login(self.staff_user)

        response = self.client.post(
            reverse("reader_workflow_return", args=(self.copy.pk,))
        )

        self.assertEqual(response.status_code, 302)
        oldest.refresh_from_db()
        newer.refresh_from_db()
        self.copy.refresh_from_db()
        self.loan.refresh_from_db()
        self.assertEqual(oldest.status, Reservation.Status.READY)
        self.assertEqual(oldest.assigned_copy, self.copy)
        self.assertEqual(oldest.hold_until, self.today + timedelta(days=3))
        self.assertEqual(newer.status, Reservation.Status.ACTIVE)
        self.assertEqual(self.copy.status, Copy.Status.RESERVED)
        self.assertEqual(self.loan.returned_at, self.today)
        self.assertTrue(
            Notification.objects.filter(
                reservation=oldest,
                reader=self.other_reader,
                kind=Notification.Kind.RESERVATION_READY,
            ).exists()
        )

    def test_expiring_hold_releases_copy_to_next_waiting_reader(self):
        self.loan.returned_at = self.today - timedelta(days=4)
        self.loan.save(update_fields=("returned_at",))
        ready = Reservation.objects.create(
            reader=self.reader,
            book=self.book,
            status=Reservation.Status.READY,
            assigned_copy=self.copy,
            ready_at=self.today - timedelta(days=4),
            hold_until=self.today - timedelta(days=1),
        )
        waiting = Reservation.objects.create(
            reader=self.other_reader,
            book=self.book,
            created_at=timezone.now() - timedelta(days=2),
        )
        self.copy.status = Copy.Status.RESERVED
        self.copy.save(update_fields=("status",))

        call_command("expire_reservations")

        ready.refresh_from_db()
        waiting.refresh_from_db()
        self.copy.refresh_from_db()
        self.assertEqual(ready.status, Reservation.Status.EXPIRED)
        self.assertIsNone(ready.assigned_copy)
        self.assertEqual(waiting.status, Reservation.Status.READY)
        self.assertEqual(waiting.assigned_copy, self.copy)
        self.assertEqual(self.copy.status, Copy.Status.RESERVED)
        self.assertEqual(waiting.hold_until, self.today + timedelta(days=3))

    def test_reader_cabinet_displays_reservations_and_notifications(self):
        reservation = Reservation.objects.create(
            reader=self.reader,
            book=self.book,
        )
        Notification.objects.create(
            reader=self.reader,
            reservation=reservation,
            kind=Notification.Kind.INFO,
            text="Workflow notification",
        )
        self.client.force_login(self.reader_user)

        response = self.client.get(reverse("reader_workflow_cabinet"))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, self.book.title)
        self.assertContains(response, "Workflow notification")

    def test_reader_can_create_reservation_when_no_copy_is_available(self):
        self.client.force_login(self.reader_user)

        response = self.client.post(
            reverse("reader_workflow_reserve", args=(self.book.pk,))
        )

        self.assertEqual(response.status_code, 302)
        self.assertTrue(
            Reservation.objects.filter(
                reader=self.reader,
                book=self.book,
                status=Reservation.Status.ACTIVE,
            ).exists()
        )

    def test_renewal_is_allowed_once_and_uses_configured_term(self):
        self.client.force_login(self.reader_user)
        url = reverse("reader_workflow_renew", args=(self.loan.pk,))

        first_response = self.client.post(url)
        self.assertEqual(first_response.status_code, 302)
        self.loan.refresh_from_db()
        original_due_date = self.today + timedelta(days=7)
        self.assertEqual(self.loan.due_date, original_due_date + timedelta(days=14))
        self.assertEqual(Renewal.objects.filter(loan=self.loan).count(), 1)

        self.client.post(url)
        self.assertEqual(Renewal.objects.filter(loan=self.loan).count(), 1)

    def test_renewal_limit_uses_library_setting(self):
        settings = LibrarySettings.get()
        settings.max_renewals = 2
        settings.save(update_fields=("max_renewals",))
        self.client.force_login(self.reader_user)
        url = reverse("reader_workflow_renew", args=(self.loan.pk,))

        self.client.post(url)
        self.client.post(url)
        self.assertEqual(Renewal.objects.filter(loan=self.loan).count(), 2)
        due_date_after_two_renewals = self.today + timedelta(days=35)
        self.loan.refresh_from_db()
        self.assertEqual(self.loan.due_date, due_date_after_two_renewals)

        self.client.post(url)
        self.assertEqual(Renewal.objects.filter(loan=self.loan).count(), 2)

    def test_overdue_loan_cannot_be_renewed(self):
        self.loan.due_date = self.today - timedelta(days=1)
        self.loan.save(update_fields=("due_date",))
        self.client.force_login(self.reader_user)

        self.client.post(reverse("reader_workflow_renew", args=(self.loan.pk,)))

        self.loan.refresh_from_db()
        self.assertEqual(self.loan.due_date, self.today - timedelta(days=1))
        self.assertFalse(Renewal.objects.filter(loan=self.loan).exists())

    def test_renewal_is_blocked_by_another_readers_reservation(self):
        Reservation.objects.create(
            reader=self.other_reader,
            book=self.book,
            status=Reservation.Status.ACTIVE,
        )
        old_due_date = self.loan.due_date
        self.client.force_login(self.reader_user)

        self.client.post(reverse("reader_workflow_renew", args=(self.loan.pk,)))

        self.loan.refresh_from_db()
        self.assertEqual(self.loan.due_date, old_due_date)
        self.assertFalse(Renewal.objects.filter(loan=self.loan).exists())

    def test_overdue_fine_report_is_staff_only_and_filters_period(self):
        self.loan.due_date = self.today - timedelta(days=5)
        self.loan.save(update_fields=("due_date",))
        Fine.objects.create(
            loan=self.loan,
            days_overdue=5,
            rate_per_day=Decimal("2.00"),
            amount=Decimal("10.00"),
            accrued_at=self.today - timedelta(days=1),
        )
        url = reverse("reader_workflow_report")
        self.client.force_login(self.reader_user)
        self.assertEqual(
            self.client.get(
                url,
                {"start_date": self.today - timedelta(days=2), "end_date": self.today},
            ).status_code,
            403,
        )

        self.client.force_login(self.staff_user)
        response = self.client.get(
            url,
            {"start_date": self.today - timedelta(days=2), "end_date": self.today},
        )

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, self.book.title)
        self.assertContains(response, "10,00")
        self.assertContains(response, "5 дн.")

    def test_overdue_report_excludes_loans_returned_before_period_end(self):
        self.loan.due_date = self.today - timedelta(days=5)
        self.loan.save(update_fields=("due_date",))
        closed_copy = Copy.objects.create(
            book=self.book,
            inventory_number="100002",
            status=Copy.Status.ON_LOAN,
        )
        Loan.objects.create(
            copy=closed_copy,
            reader=self.other_reader,
            issued_by=self.staff,
            issued_at=self.today - timedelta(days=10),
            due_date=self.today - timedelta(days=5),
            returned_at=self.today - timedelta(days=1),
            return_condition=Copy.Condition.GOOD,
        )
        self.client.force_login(self.staff_user)

        response = self.client.get(
            reverse("reader_workflow_report"),
            {
                "start_date": self.today - timedelta(days=10),
                "end_date": self.today,
            },
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.context["overdue_count"], 1)

    def test_overdue_fine_report_rejects_reversed_period(self):
        self.client.force_login(self.staff_user)

        response = self.client.get(
            reverse("reader_workflow_report"),
            {"start_date": "2026-11-13", "end_date": "2026-10-01"},
        )

        self.assertEqual(response.status_code, 200)
        self.assertContains(
            response,
            "Дата окончания не может быть раньше даты начала. Укажите корректный период.",
        )
        self.assertNotContains(response, "Просроченных выдач:")

    def test_due_reminder_command_is_idempotent(self):
        self.loan.due_date = self.today + timedelta(days=2)
        self.loan.save(update_fields=("due_date",))

        call_command("send_due_reminders", today=self.today.isoformat())
        call_command("send_due_reminders", today=self.today.isoformat())

        reminders = Notification.objects.filter(
            loan=self.loan,
            kind=Notification.Kind.DUE_SOON,
        )
        self.assertEqual(reminders.count(), 1)
        self.client.force_login(self.reader_user)
        self.assertContains(self.client.get(reverse("cabinet")), "Срок возврата")
