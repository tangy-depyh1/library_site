from django.core.paginator import Paginator
from django.db.models import Count, Q
from django.shortcuts import get_object_or_404, render
from django.contrib.auth.decorators import login_required
from django.utils import timezone
from .models import Book, BookAuthor, Genre,Fine, Reservation, Favorite
from django.conf import settings
from django.contrib import messages
from django.core.mail import send_mail
from django.shortcuts import redirect
from .forms import ContactForm
from .forms import ProfileForm
from django.views.decorators.http import require_POST
from django.http import JsonResponse



@login_required
@require_POST
def reserve(request, pk):
    book = get_object_or_404(books_qs(), pk=pk)
    reader = getattr(request.user, "reader_profile", None)
    if reader is None:
        messages.error(request, "Бронировать книги могут только читатели.")
    elif reader.is_blocked:
        messages.error(request, f"Выдача заблокирована: {reader.block_reason}")
    elif book.free > 0:
        messages.warning(request, "Свободные экземпляры есть: приходите в библиотеку с читательским билетом.")
    elif Reservation.objects.filter(reader=reader, book=book, status__in=["active", "ready"]).exists():
        messages.warning(request, "Заявка на эту книгу у вас уже есть.")
    else:
        res = Reservation.objects.create(reader=reader, book=book)
        place = Reservation.objects.filter(book=book, status="active", created_at__lte=res.created_at).count()
        messages.success(request, f"Заявка принята. Ваше место в очереди: {place}.")
    return redirect("book_detail", pk=pk)
def books_qs():
    """Книги с числом экземпляров: всего (без списанных) и свободных."""
    return (
        Book.objects.select_related("genre")
        .prefetch_related("authors")
        .annotate(
            total=Count("copies", filter=~Q(copies__status="written_off")),
            free=Count("copies", filter=Q(copies__status="in_stock")),
        )
    )


def ci(field, text):
    """Поиск без учёта регистра: SQLite не различает регистр только для латиницы."""
    cond = Q()
    for v in {text, text.lower(), text.upper(), text.capitalize(), text.title()}:
        cond |= Q(**{f"{field}__icontains": v})
    return cond

from django.contrib.auth.decorators import login_required
from django.utils import timezone

from .models import Fine
def filter_by_text(qs, text):
    by_author = BookAuthor.objects.filter(ci("author__last_name", text)).values("book_id")
    return qs.filter(ci("title", text) | Q(pk__in=by_author))


def home(request):
    new_books = books_qs().order_by("-created_at", "-id")[:4]
    return render(request, "home.html", {"new_books": new_books, "genres": Genre.objects.all()[:5]})


def catalog(request):
    qs = books_qs()
    genre = request.GET.get("genre", "")
    only_free = request.GET.get("free") == "1"
    if genre.isdigit():
        qs = qs.filter(genre_id=int(genre))
    if only_free:
        qs = qs.filter(free__gt=0)
    page = Paginator(qs.order_by("title"), 20).get_page(request.GET.get("page"))
    context = {"page": page, "genres": Genre.objects.all(), "genre": genre, "only_free": only_free}
    return render(request, "catalog.html", context)

def book_detail(request, pk):
    book = get_object_or_404(books_qs(), pk=pk)
    copies = book.copies.exclude(status="written_off").order_by("inventory_number")
    return render(request, "book_detail.html", {"book": book, "copies": copies})


def search(request):
    text = request.GET.get("q", "").strip()
    qs = books_qs()
    page = None
    if text:
        qs = filter_by_text(qs, text).order_by("title")
        page = Paginator(qs, 20).get_page(request.GET.get("page"))
    return render(request, "search.html", {"q": text, "page": page})

@login_required
def cabinet(request):
    reader = getattr(request.user, "reader_profile", None)
    if reader is None:
        return render(request, "cabinet_no_reader.html", status=403)
    loans = reader.loans.select_related("copy__book")
    context = {
        "reader": reader,
        "current": loans.filter(returned_at__isnull=True).order_by("due_date"),
        "history": loans.filter(returned_at__isnull=False)[:20],
        "fines": Fine.objects.filter(loan__reader=reader).select_related("loan__copy__book"),
        "notifications": reader.notifications.all()[:5],
        "today": timezone.localdate(),
    }
    return render(request, "cabinet.html", context)
def contacts(request):
    if request.method == "POST":
        form = ContactForm(request.POST)
        if form.is_valid():
            cd = form.cleaned_data
            send_mail(
                f"Вопрос с сайта библиотеки от {cd['name']}",
                f"E-mail: {cd['email']}\nТелефон: {cd['phone'] or '—'}\n\n{cd['message']}",
                settings.DEFAULT_FROM_EMAIL,
                [settings.LIBRARY_EMAIL],
            )
            messages.success(request, "Сообщение отправлено. Библиотекарь ответит на указанный e-mail.")
            return redirect("contacts")
    else:
        form = ContactForm()
    return render(request, "contacts.html", {"form": form})


@login_required
def profile(request):
    reader = getattr(request.user, "reader_profile", None)
    if reader is None:
        return render(request, "cabinet_no_reader.html", status=403)
    if request.method == "POST":
        form = ProfileForm(request.POST, instance=reader)
        if form.is_valid():
            form.save()
            messages.success(request, "Контактные данные сохранены.")
            return redirect("profile")
    else:
        form = ProfileForm(instance=reader)
    return render(request, "profile.html", {"form": form, "reader": reader})

def book_detail(request, pk):
    book = get_object_or_404(books_qs(), pk=pk)
    copies = book.copies.exclude(status="written_off").order_by("inventory_number")
    reader = getattr(request.user, "reader_profile", None) if request.user.is_authenticated else None
    is_favorite = bool(reader) and Favorite.objects.filter(reader=reader, book=book).exists()
    return render(request, "book_detail.html", {"book": book, "copies": copies, "is_favorite": is_favorite})



@require_POST
def favorite_toggle(request, pk):
    if not request.user.is_authenticated:
        return JsonResponse({"error": "Войдите, чтобы пользоваться избранным."}, status=401)
    reader = getattr(request.user, "reader_profile", None)
    if reader is None:
        return JsonResponse({"error": "Избранное доступно читателям."}, status=403)
    book = get_object_or_404(Book, pk=pk)
    favorite, created = Favorite.objects.get_or_create(reader=reader, book=book)
    if not created:
        favorite.delete()
    return JsonResponse({"favorite": created, "count": reader.favorites.count()})


@login_required
def favorites(request):
    reader = getattr(request.user, "reader_profile", None)
    if reader is None:
        return render(request, "cabinet_no_reader.html", status=403)
    qs = books_qs().filter(pk__in=reader.favorites.values("book_id")).order_by("title")
    return render(request, "favorites.html", {"books": qs})