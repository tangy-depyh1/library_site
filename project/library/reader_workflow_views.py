from datetime import date, timedelta
from decimal import Decimal

from django import forms
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.db import IntegrityError, transaction
from django.db.models import Q, Sum
from django.http import HttpResponseForbidden
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import path
from django.utils import timezone
from django.views.decorators.http import require_POST

from .models import (
    Book,
    Copy,
    Fine,
    LibrarySettings,
    Loan,
    Notification,
    Reader,
    Renewal,
    Reservation,
    Staff,
)


def _reader_for(request):
    return getattr(request.user, "reader_profile", None)


def _staff_for(request):
    staff = getattr(request.user, "staff_profile", None)
    if staff and staff.role in Staff.Role.values:
        return staff
    return None


def _reader_required_response(request):
    messages.error(request, "Эта операция доступна только зарегистрированным читателям.")
    return render(request, "cabinet_no_reader.html", status=403)


def _notify_reservation_ready(reservation):
    hold_until = reservation.hold_until.strftime("%d.%m.%Y")
    Notification.objects.create(
        reader=reservation.reader,
        kind=Notification.Kind.RESERVATION_READY,
        reservation=reservation,
        text=f"Книга «{reservation.book.title}» отложена до {hold_until}.",
    )


def assign_oldest_active_reservation(copy, today=None):
    """Reserve an in-stock copy for the oldest waiting reader, if one exists."""
    today = today or timezone.localdate()
    copy = Copy.objects.select_for_update().get(pk=copy.pk)
    if copy.status != Copy.Status.IN_STOCK:
        return None
    if copy.loans.filter(returned_at__isnull=True).exists():
        return None
    if copy.reservations.filter(status=Reservation.Status.READY).exists():
        return None

    reservation = (
        Reservation.objects.select_for_update()
        .filter(book_id=copy.book_id, status=Reservation.Status.ACTIVE)
        .order_by("created_at", "pk")
        .first()
    )
    if reservation is None:
        return None

    reservation.status = Reservation.Status.READY
    reservation.assigned_copy = copy
    reservation.ready_at = today
    reservation.hold_until = today + timedelta(
        days=LibrarySettings.get().reservation_hold_days
    )
    reservation.save(
        update_fields=("status", "assigned_copy", "ready_at", "hold_until")
    )
    copy.status = Copy.Status.RESERVED
    copy.save(update_fields=("status",))
    _notify_reservation_ready(reservation)
    return reservation


@login_required
def reader_workflow_cabinet(request):
    reader = _reader_for(request)
    if reader is None:
        return _reader_required_response(request)
    context = {
        "reader": reader,
        "reservations": reader.reservations.select_related(
            "book", "assigned_copy"
        ).order_by("-created_at", "-pk")[:50],
        "notifications": reader.notifications.all()[:50],
        "today": timezone.localdate(),
    }
    return render(request, "reader_workflows/cabinet.html", context)


@login_required
@require_POST
def create_reservation(request, book_id):
    reader = _reader_for(request)
    if reader is None:
        return _reader_required_response(request)

    try:
        with transaction.atomic():
            book = get_object_or_404(Book.objects.select_for_update(), pk=book_id)
            if reader.is_blocked:
                message = f"Бронирование недоступно: {reader.block_reason}"
                level = messages.error
            elif Copy.objects.filter(book=book, status=Copy.Status.IN_STOCK).exists():
                message = "Есть свободный экземпляр: бронирование не требуется."
                level = messages.warning
            elif Reservation.objects.filter(
                reader=reader,
                book=book,
                status__in=(Reservation.Status.ACTIVE, Reservation.Status.READY),
            ).exists():
                message = "У вас уже есть действующая заявка на эту книгу."
                level = messages.warning
            else:
                reservation = Reservation.objects.create(reader=reader, book=book)
                queue_position = Reservation.objects.filter(
                    book=book, status=Reservation.Status.ACTIVE
                ).filter(
                    Q(created_at__lt=reservation.created_at)
                    | Q(created_at=reservation.created_at, pk__lte=reservation.pk)
                ).count()
                message = f"Заявка принята. Место в очереди: {queue_position}."
                level = messages.success
    except IntegrityError:
        messages.warning(request, "Заявка на эту книгу уже существует.")
    else:
        level(request, message)
    return redirect("reader_workflow_cabinet")


@login_required
@require_POST
def cancel_reservation(request, reservation_id):
    reader = _reader_for(request)
    if reader is None:
        return _reader_required_response(request)

    copy_id = Reservation.objects.filter(
        pk=reservation_id, reader=reader
    ).values_list("assigned_copy_id", flat=True).first()
    with transaction.atomic():
        copy = (
            Copy.objects.select_for_update().filter(pk=copy_id).first()
            if copy_id
            else None
        )
        reservation = (
            Reservation.objects.select_for_update()
            .filter(pk=reservation_id, reader=reader)
            .first()
        )
        if reservation is None:
            messages.error(request, "Заявка не найдена.")
        elif reservation.status not in (
            Reservation.Status.ACTIVE,
            Reservation.Status.READY,
        ):
            messages.error(request, "Эту заявку уже нельзя отменить.")
        else:
            release_copy = (
                reservation.status == Reservation.Status.READY
                and copy is not None
                and copy.status == Copy.Status.RESERVED
            )
            reservation.status = Reservation.Status.CANCELLED
            reservation.assigned_copy = None
            reservation.ready_at = None
            reservation.hold_until = None
            reservation.save(
                update_fields=("status", "assigned_copy", "ready_at", "hold_until")
            )
            if release_copy:
                copy.status = Copy.Status.IN_STOCK
                copy.save(update_fields=("status",))
                assign_oldest_active_reservation(copy)
            messages.success(request, "Заявка отменена.")
    return redirect("reader_workflow_cabinet")


@login_required
@require_POST
def return_copy(request, copy_id):
    staff = _staff_for(request)
    if staff is None:
        return HttpResponseForbidden("Операция доступна только сотрудникам библиотеки.")

    condition = request.POST.get("condition", Copy.Condition.GOOD)
    if condition not in Copy.Condition.values:
        messages.error(request, "Указано неизвестное состояние экземпляра.")
        return redirect("reader_workflow_report")

    raw_return_date = request.POST.get("returned_at", "").strip()
    if raw_return_date:
        try:
            return_date = date.fromisoformat(raw_return_date)
        except ValueError:
            messages.error(request, "Укажите корректную дату возврата.")
            return redirect("reader_workflow_report")
    else:
        return_date = timezone.localdate()

    if return_date > timezone.localdate():
        messages.error(request, "Дата возврата не может быть в будущем.")
        return redirect("reader_workflow_report")

    with transaction.atomic():
        copy = get_object_or_404(
            Copy.objects.select_for_update(), pk=copy_id
        )
        loan = (
            Loan.objects.select_for_update()
            .filter(copy=copy, returned_at__isnull=True)
            .first()
        )
        if loan is None:
            messages.error(request, "Для этого экземпляра нет активной выдачи.")
        elif return_date < loan.issued_at:
            messages.error(request, "Дата возврата не может предшествовать выдаче.")
        else:
            loan.returned_at = return_date
            loan.return_condition = condition
            loan.received_by = staff
            loan.save(
                update_fields=("returned_at", "return_condition", "received_by")
            )
            copy.condition = condition
            copy.status = Copy.Status.IN_STOCK
            copy.save(update_fields=("condition", "status"))
            reservation = assign_oldest_active_reservation(copy, today=return_date)
            if reservation:
                messages.success(
                    request,
                    f"Возврат принят. Экземпляр отложен читателю из очереди "
                    f"до {reservation.hold_until:%d.%m.%Y}.",
                )
            else:
                messages.success(request, "Возврат принят; экземпляр доступен.")
    return redirect("reader_workflow_report")


def expire_ready_reservations(today=None):
    """Expire elapsed holds and hand released copies to the next waiting reader."""
    today = today or timezone.localdate()
    expired_count = 0
    reservation_ids = list(
        Reservation.objects.filter(
            status=Reservation.Status.READY, hold_until__lt=today
        )
        .order_by("hold_until", "pk")
        .values_list("pk", flat=True)
    )
    for reservation_id in reservation_ids:
        copy_id = Reservation.objects.filter(
            pk=reservation_id,
            status=Reservation.Status.READY,
            hold_until__lt=today,
        ).values_list("assigned_copy_id", flat=True).first()
        with transaction.atomic():
            copy = (
                Copy.objects.select_for_update().filter(pk=copy_id).first()
                if copy_id
                else None
            )
            reservation = (
                Reservation.objects.select_for_update()
                .filter(
                    pk=reservation_id,
                    status=Reservation.Status.READY,
                    hold_until__lt=today,
                )
                .first()
            )
            if reservation is None:
                continue
            reservation.status = Reservation.Status.EXPIRED
            reservation.assigned_copy = None
            reservation.ready_at = None
            reservation.hold_until = None
            reservation.save(
                update_fields=("status", "assigned_copy", "ready_at", "hold_until")
            )
            if copy and copy.status == Copy.Status.RESERVED:
                copy.status = Copy.Status.IN_STOCK
                copy.save(update_fields=("status",))
                assign_oldest_active_reservation(copy, today=today)
            expired_count += 1
    return expired_count


@login_required
@require_POST
def renew_loan(request, loan_id):
    reader = _reader_for(request)
    if reader is None:
        return _reader_required_response(request)

    today = timezone.localdate()
    settings = LibrarySettings.get()
    with transaction.atomic():
        loan = (
            Loan.objects.select_for_update()
            .filter(pk=loan_id, reader=reader)
            .first()
        )
        if loan is None:
            messages.error(request, "Выдача не найдена.")
        elif loan.returned_at is not None:
            messages.error(request, "Возвращённую книгу нельзя продлить.")
        elif loan.due_date is None or loan.due_date < today:
            messages.error(request, "Просроченную книгу нельзя продлить.")
        elif settings.max_renewals < 1:
            messages.error(request, "Продление отключено настройками библиотеки.")
        elif loan.renewals.count() >= settings.max_renewals:
            if settings.max_renewals == 1:
                messages.error(request, "Продление уже использовано.")
            else:
                messages.error(request, "Достигнуто максимальное число продлений.")
        elif Reservation.objects.filter(
            book=loan.copy.book,
            status__in=(Reservation.Status.ACTIVE, Reservation.Status.READY),
        ).exclude(reader=reader).exists():
            messages.error(request, "Другой читатель ожидает эту книгу; продление недоступно.")
        else:
            previous_due_date = loan.due_date
            new_due_date = previous_due_date + timedelta(
                days=settings.renewal_days
            )
            loan.due_date = new_due_date
            loan.save(update_fields=("due_date",))
            Renewal.objects.create(
                loan=loan,
                renewed_at=today,
                previous_due_date=previous_due_date,
                new_due_date=new_due_date,
            )
            messages.success(
                request, f"Книга продлена до {new_due_date:%d.%m.%Y}."
            )
    return redirect("reader_workflow_cabinet")


class ReportRangeForm(forms.Form):
    start_date = forms.DateField(
        label="С даты",
        widget=forms.DateInput(attrs={"type": "date"}),
    )
    end_date = forms.DateField(
        label="По дату",
        widget=forms.DateInput(attrs={"type": "date"}),
    )

    def clean(self):
        cleaned_data = super().clean()
        start_date = cleaned_data.get("start_date")
        end_date = cleaned_data.get("end_date")
        if start_date and end_date and start_date > end_date:
            raise forms.ValidationError("Дата начала позже даты окончания.")
        return cleaned_data


@login_required
def overdue_fines_report(request):
    if _staff_for(request) is None:
        return HttpResponseForbidden("Отчёт доступен только сотрудникам библиотеки.")

    today = timezone.localdate()
    initial = {"start_date": today.replace(day=1), "end_date": today}
    form = ReportRangeForm(request.GET or initial)
    overdue_loans = []
    fines = Fine.objects.none()
    fine_totals = {
        "all": Decimal("0.00"),
        "paid": Decimal("0.00"),
        "unpaid": Decimal("0.00"),
    }
    if form.is_valid():
        start_date = form.cleaned_data["start_date"]
        end_date = form.cleaned_data["end_date"]
        loans = (
            Loan.objects.filter(due_date__lt=end_date)
            .filter(Q(returned_at__isnull=True) | Q(returned_at__gt=end_date))
            .select_related("reader", "copy__book")
            .order_by("due_date", "pk")
        )
        for loan in loans:
            overdue_days = max((end_date - loan.due_date).days, 0)
            if overdue_days:
                loan.report_overdue_days = overdue_days
                overdue_loans.append(loan)
        fines = (
            Fine.objects.filter(accrued_at__range=(start_date, end_date))
            .select_related("loan__reader", "loan__copy__book")
            .order_by("-accrued_at", "-pk")
        )
        fine_totals["all"] = fines.aggregate(total=Sum("amount"))["total"] or Decimal("0.00")
        fine_totals["paid"] = (
            fines.filter(status=Fine.Status.PAID).aggregate(total=Sum("amount"))["total"]
            or Decimal("0.00")
        )
        fine_totals["unpaid"] = (
            fines.filter(status=Fine.Status.UNPAID).aggregate(total=Sum("amount"))["total"]
            or Decimal("0.00")
        )
    return render(
        request,
        "reader_workflows/report.html",
        {
            "form": form,
            "overdue_loans": overdue_loans,
            "overdue_count": len(overdue_loans),
            "fines": fines,
            "fine_totals": fine_totals,
            "staff": _staff_for(request),
        },
    )


urlpatterns = [
    path("cabinet/reservations/", reader_workflow_cabinet, name="reader_workflow_cabinet"),
    path("catalog/book/<int:book_id>/reserve/", create_reservation, name="reader_workflow_reserve"),
    path(
        "cabinet/reservations/<int:reservation_id>/cancel/",
        cancel_reservation,
        name="reader_workflow_cancel_reservation",
    ),
    path("cabinet/loans/<int:loan_id>/renew/", renew_loan, name="reader_workflow_renew"),
    path("staff/copies/<int:copy_id>/return/", return_copy, name="reader_workflow_return"),
    path("staff/reports/overdue/", overdue_fines_report, name="reader_workflow_report"),
]
