from django.db.models import Count, Q
from django.shortcuts import render

from .models import Book, Genre


def home(request):
    new_books = (
        Book.objects.select_related("genre")
        .prefetch_related("authors")
        .annotate(
            total=Count("copies", filter=~Q(copies__status="written_off")),
            free=Count("copies", filter=Q(copies__status="in_stock")),
        )
        .order_by("-created_at", "-id")[:4]
    )
    genres = Genre.objects.all()[:5]
    return render(request, "home.html", {"new_books": new_books, "genres": genres})

def catalog(request):
    return render(request, "stub.html", {"title": "Каталог"})

def rules(request):
    return render(request, "stub.html", {"title": "Правила пользования"})

def login_page(request):
    return render(request, "stub.html", {"title": "Вход"})