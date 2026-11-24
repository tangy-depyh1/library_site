from datetime import timedelta
from decimal import Decimal
from functools import wraps

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.exceptions import ObjectDoesNotExist
from django.db import IntegrityError, transaction
from django.db.models import Q, Sum
from django.db.models.deletion import ProtectedError
from django.http import HttpResponseForbidden
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import path
from django.utils import timezone
from django.views.decorators.http import require_POST

from .models import (
    Author,
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
from .reader_workflow_views import assign_oldest_active_reservation, expire_ready_reservations
from .staff_forms import (
    AuthorForm,
    BookForm,
    CopyForm,
    GenreForm,
    IssueLoanForm,
    LibrarySettingsForm,
    ReaderRegistrationForm,
    ReturnLoanForm,
    StaffAccountCreationForm,
)


def librarian_required(view_func):
    """Require an authenticated staff profile with the librarian role."""
    @wraps(view_func)
    @login_required
    def wrapped(request, *args, **kwargs):
        try:
            profile = request.user.staff_profile
        except (AttributeError, ObjectDoesNotExist):
            return HttpResponseForbidden("Доступ разрешён только библиотекарям.")
        if profile.role != Staff.Role.LIBRARIAN:
            return HttpResponseForbidden("Доступ разрешён только библиотекарям.")
        return view_func(request, *args, **kwargs)

    return wrapped


def administrator_required(view_func):
    """Require an authenticated staff profile with the administrator role."""
    @wraps(view_func)
    @login_required
    def wrapped(request, *args, **kwargs):
        try:
            profile = request.user.staff_profile
        except (AttributeError, ObjectDoesNotExist):
            return HttpResponseForbidden("Доступ разрешён только администраторам.")
        if profile.role != Staff.Role.ADMIN:
            return HttpResponseForbidden("Доступ разрешён только администраторам.")
        return view_func(request, *args, **kwargs)

    return wrapped


def _issuance_block_reason(reader, today):
    overdue_exists = Loan.objects.filter(
        reader=reader,
        returned_at__isnull=True,
        due_date__lt=today,
    ).exists()
    unpaid_total = (
        Fine.objects.filter(loan__reader=reader, status=Fine.Status.UNPAID)
        .aggregate(total=Sum("amount"))["total"]
        or Decimal("0.00")
    )
    if not reader.is_blocked and not overdue_exists and not unpaid_total:
        return ""
    reasons = [reader.block_reason] if reader.block_reason else []
    if overdue_exists:
        reasons.append("Есть открытая просроченная выдача.")
    if unpaid_total:
        amount = format(unpaid_total.normalize(), "f")
        if not any(amount in reason for reason in reasons):
            reasons.append(f"Не оплачен штраф: {amount} руб.")
    if not reasons and reader.is_blocked:
        reasons.append("Читатель заблокирован.")
    return "Выдача невозможна: " + "; ".join(reasons)


@librarian_required
def staff_dashboard(request):
    context = {
        "readers_count": Reader.objects.count(),
        "open_loans": Loan.objects.filter(returned_at__isnull=True).select_related(
            "reader", "copy__book"
        )[:10],
        "unpaid_fines_count": Fine.objects.filter(status=Fine.Status.UNPAID).count(),
    }
    return render(request, "library/staff/dashboard.html", context)


@librarian_required
def staff_readers(request):
    query = request.GET.get("q", "").strip()
    readers = Reader.objects.all()
    if query:
        readers = readers.filter(
            Q(card_number__icontains=query) | Q(full_name__icontains=query)
        )
    return render(
        request,
        "library/staff/readers.html",
        {"readers": readers, "query": query},
    )


@librarian_required
def staff_reader_create(request):
    if request.method == "POST":
        form = ReaderRegistrationForm(request.POST)
        if form.is_valid():
            try:
                with transaction.atomic():
                    form.save()
            except IntegrityError:
                form.add_error("card_number", "Читательский билет с таким номером уже зарегистрирован.")
            else:
                messages.success(request, "Читатель зарегистрирован.")
                return redirect("staff_readers")
    else:
        form = ReaderRegistrationForm()
    return render(
        request,
        "library/staff/form.html",
        {"form": form, "title": "Регистрация читателя", "cancel_url": "staff_readers"},
    )


@librarian_required
def staff_catalog(request):
    return render(
        request,
        "library/staff/catalog.html",
        {
            "book_count": Book.objects.count(),
            "copy_count": Copy.objects.count(),
            "author_count": Author.objects.count(),
            "genre_count": Genre.objects.count(),
        },
    )


def _catalog_list(request, model, title, list_url_name, add_url_name, edit_url_name, delete_url_name):
    query = request.GET.get("q", "").strip()
    objects = model.objects.all()
    if query:
        searchable = {
            Book: Q(title__icontains=query) | Q(isbn__icontains=query),
            Author: (
                Q(last_name__icontains=query)
                | Q(first_name__icontains=query)
                | Q(middle_name__icontains=query)
            ),
            Genre: Q(name__icontains=query),
            Copy: (
                Q(inventory_number__icontains=query)
                | Q(book__title__icontains=query)
            ),
        }[model]
        objects = objects.filter(searchable)
    return render(
        request,
        "library/staff/catalog_list.html",
        {
            "objects": objects,
            "query": query,
            "title": title,
            "list_url_name": list_url_name,
            "add_url_name": add_url_name,
            "edit_url_name": edit_url_name,
            "delete_url_name": delete_url_name,
        },
    )


def _catalog_form(request, model, form_class, title, list_url_name, instance=None):
    form = form_class(request.POST or None, instance=instance)
    if request.method == "POST" and form.is_valid():
        try:
            with transaction.atomic():
                form.save()
        except IntegrityError:
            form.add_error(None, "Запись с такими данными уже существует.")
        else:
            messages.success(request, f"{title}: изменения сохранены.")
            return redirect(list_url_name)
    return render(
        request,
        "library/staff/form.html",
        {"form": form, "title": title, "cancel_url": list_url_name},
    )


def _catalog_delete(request, instance, title, list_url_name):
    if request.method == "POST":
        try:
            with transaction.atomic():
                instance.delete()
        except ProtectedError:
            messages.error(request, "Нельзя удалить запись, используемую в библиотечном учёте.")
        else:
            messages.success(request, f"{title} удалена.")
        return redirect(list_url_name)
    return render(
        request,
        "library/staff/confirm_delete.html",
        {"object": instance, "title": f"Удаление: {title}", "cancel_url": list_url_name},
    )


@librarian_required
def staff_books(request):
    return _catalog_list(
        request, Book, "Книги", "staff_books", "staff_book_create",
        "staff_book_edit", "staff_book_delete",
    )


@librarian_required
def staff_book_create(request):
    return _catalog_form(request, Book, BookForm, "Книга", "staff_books")


@librarian_required
def staff_book_edit(request, pk):
    return _catalog_form(
        request, Book, BookForm, "Книга", "staff_books",
        get_object_or_404(Book, pk=pk),
    )


@librarian_required
def staff_book_delete(request, pk):
    return _catalog_delete(request, get_object_or_404(Book, pk=pk), "Книга", "staff_books")


@librarian_required
def staff_authors(request):
    return _catalog_list(
        request, Author, "Авторы", "staff_authors", "staff_author_create",
        "staff_author_edit", "staff_author_delete",
    )


@librarian_required
def staff_author_create(request):
    return _catalog_form(request, Author, AuthorForm, "Автор", "staff_authors")


@librarian_required
def staff_author_edit(request, pk):
    return _catalog_form(
        request, Author, AuthorForm, "Автор", "staff_authors",
        get_object_or_404(Author, pk=pk),
    )


@librarian_required
def staff_author_delete(request, pk):
    return _catalog_delete(request, get_object_or_404(Author, pk=pk), "Автор", "staff_authors")


@librarian_required
def staff_genres(request):
    return _catalog_list(
        request, Genre, "Жанры", "staff_genres", "staff_genre_create",
        "staff_genre_edit", "staff_genre_delete",
    )


@librarian_required
def staff_genre_create(request):
    return _catalog_form(request, Genre, GenreForm, "Жанр", "staff_genres")


@librarian_required
def staff_genre_edit(request, pk):
    return _catalog_form(
        request, Genre, GenreForm, "Жанр", "staff_genres",
        get_object_or_404(Genre, pk=pk),
    )


@librarian_required
def staff_genre_delete(request, pk):
    return _catalog_delete(request, get_object_or_404(Genre, pk=pk), "Жанр", "staff_genres")


@librarian_required
def staff_copies(request):
    return _catalog_list(
        request, Copy, "Экземпляры", "staff_copies", "staff_copy_create",
        "staff_copy_edit", "staff_copy_delete",
    )


@librarian_required
def staff_copy_create(request):
    return _catalog_form(request, Copy, CopyForm, "Экземпляр", "staff_copies")


@librarian_required
def staff_copy_edit(request, pk):
    return _catalog_form(
        request, Copy, CopyForm, "Экземпляр", "staff_copies",
        get_object_or_404(Copy, pk=pk),
    )


@librarian_required
def staff_copy_delete(request, pk):
    return _catalog_delete(request, get_object_or_404(Copy, pk=pk), "Экземпляр", "staff_copies")


@librarian_required
def staff_issue(request):
    if request.method == "POST":
        form = IssueLoanForm(request.POST)
        if form.is_valid():
            card_number = form.cleaned_data["card_number"].strip()
            inventory_number = form.cleaned_data["inventory_number"].strip()
            try:
                with transaction.atomic():
                    reader = Reader.objects.select_for_update().get(card_number=card_number)
                    copy = Copy.objects.select_for_update().select_related("book").get(
                        inventory_number=inventory_number
                    )
                    today = timezone.localdate()
                    block_reason = _issuance_block_reason(reader, today)
                    if block_reason:
                        raise ValueError(block_reason)
                    reservation = (
                        Reservation.objects.select_for_update()
                        .filter(
                            assigned_copy=copy,
                            status=Reservation.Status.READY,
                        )
                        .first()
                    )
                    if copy.status == Copy.Status.RESERVED and (
                        reservation is None or reservation.reader_id != reader.pk
                    ):
                        raise ValueError("Экземпляр зарезервирован для другого читателя.")
                    if copy.status not in (Copy.Status.IN_STOCK, Copy.Status.RESERVED):
                        raise ValueError("Экземпляр не находится в фонде и не может быть выдан.")
                    if Loan.objects.filter(copy=copy, returned_at__isnull=True).exists():
                        raise ValueError("Для этого экземпляра уже зарегистрирована открытая выдача.")
                    settings = LibrarySettings.get()
                    loan = Loan.objects.create(
                        copy=copy,
                        reader=reader,
                        issued_by=request.user.staff_profile,
                        issued_at=today,
                        due_date=today + timedelta(days=settings.loan_days),
                        reservation=reservation,
                    )
                    copy.status = Copy.Status.ON_LOAN
                    copy.save(update_fields=["status"])
                    if reservation is not None:
                        reservation.status = Reservation.Status.FULFILLED
                        reservation.save(update_fields=["status"])
            except Reader.DoesNotExist:
                form.add_error("card_number", "Читатель с таким номером билета не найден.")
            except Copy.DoesNotExist:
                form.add_error("inventory_number", "Экземпляр с таким инвентарным номером не найден.")
            except ValueError as exc:
                form.add_error(None, str(exc))
            except IntegrityError:
                form.add_error(None, "Выдачу не удалось сохранить. Обновите страницу и повторите попытку.")
            else:
                messages.success(request, f"Книга выдана до {loan.due_date:%d.%m.%Y}.")
                return redirect("staff_issue")
    else:
        form = IssueLoanForm(
            initial={
                "card_number": request.GET.get("card_number", ""),
                "inventory_number": request.GET.get("inventory_number", ""),
            }
        )
    return render(request, "library/staff/issue.html", {"form": form})


@librarian_required
def staff_return(request):
    if request.method == "POST":
        form = ReturnLoanForm(request.POST)
        if form.is_valid():
            inventory_number = form.cleaned_data["inventory_number"].strip()
            condition = form.cleaned_data["condition"]
            try:
                with transaction.atomic():
                    loan = (
                        Loan.objects.select_for_update()
                        .select_related("copy", "reader")
                        .get(copy__inventory_number=inventory_number, returned_at__isnull=True)
                    )
                    copy = Copy.objects.select_for_update().get(pk=loan.copy_id)
                    today = timezone.localdate()
                    loan.returned_at = today
                    loan.return_condition = condition
                    loan.received_by = request.user.staff_profile
                    loan.save(update_fields=["returned_at", "return_condition", "received_by"])

                    copy.condition = condition
                    copy.status = Copy.Status.IN_STOCK
                    copy.save(update_fields=["condition", "status"])
                    reservation = assign_oldest_active_reservation(copy, today=today)

                    overdue_days = max((today - loan.due_date).days, 0)
                    fine = None
                    if overdue_days:
                        rate = LibrarySettings.get().fine_per_day
                        amount = (Decimal(overdue_days) * rate).quantize(Decimal("0.01"))
                        fine = Fine.objects.create(
                            loan=loan,
                            days_overdue=overdue_days,
                            rate_per_day=rate,
                            amount=amount,
                        )
                        loan.reader.is_blocked = True
                        loan.reader.block_reason = (
                            f"Просрочка по выдаче №{loan.pk}; штраф {amount} руб."
                        )[:200]
                        loan.reader.save(update_fields=["is_blocked", "block_reason"])
            except Loan.DoesNotExist:
                form.add_error(
                    "inventory_number",
                    "Открытая выдача для этого инвентарного номера не найдена.",
                )
            except IntegrityError:
                form.add_error(None, "Возврат не удалось сохранить. Обновите страницу и повторите попытку.")
            else:
                if fine:
                    messages.warning(
                        request,
                        f"Возврат зарегистрирован. Просрочка: {fine.days_overdue} дн.; "
                        f"штраф: {fine.amount} руб. Читатель заблокирован.",
                    )
                elif reservation:
                    messages.success(
                        request,
                        f"Возврат зарегистрирован. Экземпляр отложен читателю из очереди "
                        f"до {reservation.hold_until:%d.%m.%Y}.",
                    )
                else:
                    messages.success(request, "Возврат зарегистрирован без просрочки.")
                return redirect("staff_return")
    else:
        form = ReturnLoanForm()
    return render(request, "library/staff/return.html", {"form": form})


@librarian_required
def staff_fines(request):
    fines = Fine.objects.select_related(
        "loan__reader", "loan__copy__book", "accepted_by"
    )
    status = request.GET.get("status", "")
    if status in {Fine.Status.UNPAID, Fine.Status.PAID}:
        fines = fines.filter(status=status)
    return render(
        request,
        "library/staff/fines.html",
        {"fines": fines, "status": status, "status_choices": Fine.Status.choices},
    )


@librarian_required
def staff_reservations(request):
    expire_ready_reservations()
    reservations = Reservation.objects.filter(
        status__in=(Reservation.Status.ACTIVE, Reservation.Status.READY)
    ).select_related("reader", "book", "assigned_copy")
    return render(
        request,
        "library/staff/reservations.html",
        {"reservations": reservations},
    )


@librarian_required
@require_POST
def staff_fine_pay(request, pk):
    with transaction.atomic():
        fine = get_object_or_404(
            Fine.objects.select_for_update().select_related("loan__reader"),
            pk=pk,
        )
        if fine.status == Fine.Status.PAID:
            messages.info(request, "Этот штраф уже отмечен как оплаченный.")
        else:
            fine.status = Fine.Status.PAID
            fine.paid_at = timezone.localdate()
            fine.accepted_by = request.user.staff_profile
            fine.save(update_fields=["status", "paid_at", "accepted_by"])
            reader = Reader.objects.select_for_update().get(pk=fine.loan.reader_id)
            outstanding = Fine.objects.filter(
                loan__reader=reader, status=Fine.Status.UNPAID
            ).exists()
            overdue_exists = Loan.objects.filter(
                reader=reader,
                returned_at__isnull=True,
                due_date__lt=timezone.localdate(),
            ).exists()
            if (
                not outstanding
                and not overdue_exists
                and reader.block_reason.startswith("Просрочка по выдаче")
            ):
                reader.is_blocked = False
                reader.block_reason = ""
                reader.save(update_fields=["is_blocked", "block_reason"])
            messages.success(request, "Оплата штрафа зарегистрирована.")
    return redirect("staff_fines")


@administrator_required
def staff_settings(request):
    settings = LibrarySettings.get()
    if request.method == "POST":
        form = LibrarySettingsForm(request.POST, instance=settings)
        if form.is_valid():
            with transaction.atomic():
                form.save()
            messages.success(request, "Настройки библиотеки сохранены.")
            return redirect("staff_settings")
    else:
        form = LibrarySettingsForm(instance=settings)
    return render(
        request,
        "library/staff/form.html",
        {"form": form, "title": "Настройки библиотеки", "cancel_url": "staff_accounts"},
    )


@administrator_required
def staff_accounts(request):
    if request.method == "POST":
        form = StaffAccountCreationForm(request.POST)
        if form.is_valid():
            form.save()
            messages.success(request, "Учётная запись сотрудника создана.")
            return redirect("staff_accounts")
    else:
        form = StaffAccountCreationForm()
    return render(
        request,
        "library/staff/accounts.html",
        {
            "form": form,
            "staff_accounts": Staff.objects.select_related("user").all(),
        },
    )


urlpatterns = [
    # Staff entry points
    path("staff/", staff_dashboard, name="staff_dashboard"),
    path("staff/readers/", staff_readers, name="staff_readers"),
    path("staff/readers/new/", staff_reader_create, name="staff_reader_create"),
    path("staff/catalog/", staff_catalog, name="staff_catalog"),
    path("staff/catalog/books/", staff_books, name="staff_books"),
    path("staff/catalog/books/add/", staff_book_create, name="staff_book_create"),
    path("staff/catalog/books/<int:pk>/edit/", staff_book_edit, name="staff_book_edit"),
    path("staff/catalog/books/<int:pk>/delete/", staff_book_delete, name="staff_book_delete"),
    path("staff/catalog/authors/", staff_authors, name="staff_authors"),
    path("staff/catalog/authors/add/", staff_author_create, name="staff_author_create"),
    path("staff/catalog/authors/<int:pk>/edit/", staff_author_edit, name="staff_author_edit"),
    path("staff/catalog/authors/<int:pk>/delete/", staff_author_delete, name="staff_author_delete"),
    path("staff/catalog/genres/", staff_genres, name="staff_genres"),
    path("staff/catalog/genres/add/", staff_genre_create, name="staff_genre_create"),
    path("staff/catalog/genres/<int:pk>/edit/", staff_genre_edit, name="staff_genre_edit"),
    path("staff/catalog/genres/<int:pk>/delete/", staff_genre_delete, name="staff_genre_delete"),
    path("staff/catalog/copies/", staff_copies, name="staff_copies"),
    path("staff/catalog/copies/add/", staff_copy_create, name="staff_copy_create"),
    path("staff/catalog/copies/<int:pk>/edit/", staff_copy_edit, name="staff_copy_edit"),
    path("staff/catalog/copies/<int:pk>/delete/", staff_copy_delete, name="staff_copy_delete"),
    path("staff/loans/new/", staff_issue, name="staff_issue"),
    path("staff/returns/", staff_return, name="staff_return"),
    path("staff/reservations/", staff_reservations, name="staff_reservations"),
    path("staff/fines/", staff_fines, name="staff_fines"),
    path("staff/fines/<int:pk>/pay/", staff_fine_pay, name="staff_fine_pay"),
    path("staff/settings/", staff_settings, name="staff_settings"),
    path("staff/accounts/", staff_accounts, name="staff_accounts"),
]
