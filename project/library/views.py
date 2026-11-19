from django.core.paginator import Paginator
from django.db.models import Count, Q
from django.shortcuts import get_object_or_404, render
from django.contrib.auth.decorators import login_required
from django.utils import timezone

from .models import Book, BookAuthor, Genre,Fine


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