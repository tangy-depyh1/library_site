# -*- coding: utf-8 -*-
"""Наполнение базы тестовыми данными: python manage.py seed_data [--today ГГГГ-ММ-ДД] [--books 120] [--readers 100] [--seed 42] [--clear]

Данные детерминированы: одинаковые параметры дают одинаковую базу.
Учётные записи для проверки (только для тестирования!): admin, librarian1, librarian2, reader_<номер билета> — пароль TestPass123!
"""
from datetime import date, datetime

from django.contrib.auth import get_user_model
from django.core.management.base import BaseCommand, CommandError
from django.core.management.color import no_style
from django.db import connection, transaction
from django.utils import timezone

from library import models as m
from library.seed_logic import build

PASSWORD = "TestPass123!"


def aware(v):
    return timezone.make_aware(v) if isinstance(v, datetime) and timezone.is_naive(v) else v


class Command(BaseCommand):
    help = "Создаёт тестовые данные: каталог, экземпляры, читателей, выдачи, штрафы, заявки, уведомления"

    def add_arguments(self, parser):
        parser.add_argument("--today", type=date.fromisoformat, default=None, help="Опорная дата ГГГГ-ММ-ДД (по умолчанию сегодня)")
        parser.add_argument("--books", type=int, default=120, help="Число книг (для замера NFR-01 укажите 1000)")
        parser.add_argument("--readers", type=int, default=100, help="Число читателей")
        parser.add_argument("--seed", type=int, default=42, help="Зерно генератора случайных чисел")
        parser.add_argument("--clear", action="store_true", help="Удалить существующие данные библиотеки перед наполнением")

    @transaction.atomic
    def handle(self, *args, **o):
        User = get_user_model()
        if o["clear"]:
            for model in (m.Favorite, m.Notification, m.Fine, m.Renewal, m.Loan, m.Reservation, m.Reader, m.Staff,
                          m.Copy, m.BookAuthor, m.Book, m.Author, m.Genre, m.LibrarySettings):
                model.objects.all().delete()
            User.objects.filter(username__regex=r"^(admin|librarian\d+|reader_\d{6})$").delete()
        if m.Book.objects.exists() or m.Reader.objects.exists():
            raise CommandError("В базе уже есть данные. Запустите команду с ключом --clear.")
        today = o["today"] or date.today()
        T, users = build(today, books=o["books"], readers=o["readers"], seed=o["seed"])

        for key, model in (("genre", m.Genre), ("author", m.Author)):
            model.objects.bulk_create([model(**r) for r in T[key]])
        books = [m.Book(**r) for r in T["book"]]
        book_created_at = [aware(book.created_at) for book in books]
        m.Book.objects.bulk_create(books)
        for b, created_at in zip(books, book_created_at):
            b.created_at = created_at
        m.Book.objects.bulk_update(books, ["created_at"])
        m.BookAuthor.objects.bulk_create([m.BookAuthor(**r) for r in T["bookauthor"]])
        m.Copy.objects.bulk_create([m.Copy(**r) for r in T["copy"]])

        uid = {}
        for i, (username, role, _) in enumerate(users, 1):
            user = User.objects.create_user(username=username, password=PASSWORD)
            if username == "admin":
                user.is_staff = user.is_superuser = True
                user.save()
            uid[i] = user.pk
        for r in T["staff"]:
            r = dict(r); r["user_id"] = uid[r.pop("user_idx")]
            m.Staff.objects.create(**r)
        readers = []
        for r in T["reader"]:
            r = dict(r); idx = r.pop("user_idx"); r["user_id"] = uid[idx] if idx else None
            readers.append(m.Reader(**r))
        m.Reader.objects.bulk_create(readers)
        m.LibrarySettings(**T["settings"][0]).save()

        m.Reservation.objects.bulk_create([m.Reservation(**{**r, "created_at": aware(r["created_at"])}) for r in T["reservation"]])
        m.Loan.objects.bulk_create([m.Loan(**r) for r in T["loan"]])
        m.Renewal.objects.bulk_create([m.Renewal(**r) for r in T["renewal"]])
        m.Fine.objects.bulk_create([m.Fine(**r) for r in T["fine"]])
        notes = [m.Notification(**r) for r in T["notification"]]
        m.Notification.objects.bulk_create(notes)
        for n in notes:
            n.created_at = aware(n.created_at)
        m.Notification.objects.bulk_update(notes, ["created_at"])
        favs = [m.Favorite(**r) for r in T["favorite"]]
        m.Favorite.objects.bulk_create(favs)
        for f in favs:
            f.added_at = aware(f.added_at)
        m.Favorite.objects.bulk_update(favs, ["added_at"])

        # после вставки с явными id сбрасываем счётчики (важно для PostgreSQL)
        with connection.cursor() as cur:
            for sql in connection.ops.sequence_reset_sql(no_style(), [m.Genre, m.Author, m.Book, m.BookAuthor, m.Copy, m.Staff, m.Reader,
                                                                       m.Reservation, m.Loan, m.Renewal, m.Fine, m.Notification, m.Favorite]):
                cur.execute(sql)
        counts = {k: len(v) for k, v in T.items()}
        self.stdout.write(self.style.SUCCESS("Готово: " + ", ".join(f"{k}={v}" for k, v in counts.items())))
