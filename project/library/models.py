import django
from django.conf import settings
from django.core.validators import MaxValueValidator, MinValueValidator, RegexValidator
from django.db import models
from django.db.models import F, Q
from django.utils import timezone


digits6 = RegexValidator(r"^\d{6}$", "Нужно ровно 6 цифр.")
isbn_validator = RegexValidator(
    r"^(?:\d{9}[\dX]|\d{13})$",
    "ISBN должен быть 10 или 13 цифр (допускается X в ISBN-10).",
)

class Genre(models.Model):
    name = models.CharField("Название жанра", max_length=60, unique=True)
    description = models.TextField("Описание", blank=True)

    class Meta:
        verbose_name = "Жанр"
        verbose_name_plural = "Жанры"
        ordering = ["name"]

    def __str__(self):
        return self.name


class Author(models.Model):
    last_name = models.CharField("Фамилия", max_length=80)
    first_name = models.CharField("Имя", max_length=80)
    middle_name = models.CharField("Отчество", max_length=80, blank=True)
    birth_year = models.PositiveSmallIntegerField(
        "Год рождения", null=True, blank=True,
        validators=[MinValueValidator(1000), MaxValueValidator(2100)])

    class Meta:
        verbose_name = "Автор"
        verbose_name_plural = "Авторы"
        ordering = ["last_name", "first_name"]
        constraints = [
            models.UniqueConstraint(
                fields=["last_name", "first_name", "middle_name", "birth_year"],
                condition=Q(birth_year__isnull=False),
                name="unique_author_with_birth_year",
            ),
            models.UniqueConstraint(
                fields=["last_name", "first_name", "middle_name"],
                condition=Q(birth_year__isnull=True),
                name="unique_author_without_birth_year",
            ),
        ]

    @property
    def short_name(self):
        initials = f"{self.first_name[:1]}."
        if self.middle_name:
            initials += f"{self.middle_name[:1]}."
        return f"{self.last_name} {initials}"

    def __str__(self):
        return self.short_name


class Book(models.Model):
    title = models.CharField("Название", max_length=255)
    genre = models.ForeignKey(Genre, verbose_name="Жанр", on_delete=models.PROTECT, related_name="books")
    authors = models.ManyToManyField(Author, verbose_name="Авторы", through="BookAuthor", related_name="books")
    """International Standard Book Number или Международный стандартный книжный номер"""
    isbn = models.CharField("ISBN", max_length=17, unique=True, null=True, blank=True,
                            validators=[isbn_validator])
    publisher = models.CharField("Издательство", max_length=150, blank=True)
    year_published = models.PositiveSmallIntegerField(
        "Год издания", validators=[MinValueValidator(1500), MaxValueValidator(2100)])
    pages = models.PositiveSmallIntegerField("Число страниц", null=True, blank=True,
                                             validators=[MinValueValidator(1)])
    description = models.TextField("Описание", blank=True)
    created_at = models.DateTimeField("Добавлена в каталог", auto_now_add=True)

    class Meta:
        verbose_name = "Книга"
        verbose_name_plural = "Книги"
        ordering = ["title"]
        indexes = [models.Index(fields=["title"], name="book_title_idx")]
        constraints = [
            models.CheckConstraint(condition=Q(year_published__gte=1500) & Q(year_published__lte=2100),
                                   name="book_year_range"),
        ]

    def __str__(self):
        return self.title


class BookAuthor(models.Model):
    """Связующая таблица «многие ко многим» Книга — Автор с атрибутом position."""
    book = models.ForeignKey(Book, verbose_name="Книга", on_delete=models.CASCADE, related_name="book_authors")
    author = models.ForeignKey(Author, verbose_name="Автор", on_delete=models.PROTECT, related_name="book_authors")
    position = models.PositiveSmallIntegerField("Порядок автора", default=1, validators=[MinValueValidator(1)])

    class Meta:
        verbose_name = "Автор книги"
        verbose_name_plural = "Авторы книг"
        ordering = ["book", "position"]
        constraints = [
            models.UniqueConstraint(fields=["book", "author"], name="unique_book_author"),
            models.UniqueConstraint(fields=["book", "position"], name="unique_book_author_position"),
            models.CheckConstraint(condition=Q(position__gte=1), name="bookauthor_position_min"),
        ]

    def __str__(self):
        return f"{self.book} — {self.author}"


class Copy(models.Model):
    class Status(models.TextChoices):
        IN_STOCK = "in_stock", "В фонде"
        ON_LOAN = "on_loan", "Выдан"
        RESERVED = "reserved", "Забронирован"
        WRITTEN_OFF = "written_off", "Списан"

    class Condition(models.TextChoices):
        GOOD = "good", "Хорошее"
        WORN = "worn", "Изношен"
        DAMAGED = "damaged", "Повреждён"

    book = models.ForeignKey(Book, verbose_name="Книга", on_delete=models.PROTECT, related_name="copies")
    inventory_number = models.CharField("Инвентарный номер", max_length=6, unique=True, validators=[digits6])
    status = models.CharField("Статус", max_length=12, choices=Status.choices, default=Status.IN_STOCK)
    condition = models.CharField("Состояние", max_length=10, choices=Condition.choices, default=Condition.GOOD)
    shelf_location = models.CharField("Место на полке", max_length=30, blank=True)
    acquired_date = models.DateField("Дата поступления", null=True, blank=True)
    written_off_date = models.DateField("Дата списания", null=True, blank=True)

    class Meta:
        verbose_name = "Экземпляр"
        verbose_name_plural = "Экземпляры"
        ordering = ["inventory_number"]
        constraints = [
            models.CheckConstraint(
                condition=(
                    Q(status="written_off", written_off_date__isnull=False)
                    | (~Q(status="written_off") & Q(written_off_date__isnull=True))
                ),
                name="copy_writeoff_date_consistent"),
        ]

    def __str__(self):
        return f"{self.inventory_number} — {self.book}"


class Reader(models.Model):
    user = models.OneToOneField(settings.AUTH_USER_MODEL, verbose_name="Учётная запись", on_delete=models.CASCADE,
                                null=True, blank=True, related_name="reader_profile")
    card_number = models.CharField("Номер читательского билета", max_length=6, unique=True, validators=[digits6])
    full_name = models.CharField("ФИО", max_length=150)
    group_name = models.CharField("Учебная группа", max_length=20, blank=True)
    phone = models.CharField("Телефон", max_length=20, blank=True)
    email = models.EmailField("E-mail", blank=True)
    registered_at = models.DateField("Дата регистрации", default=timezone.localdate)
    is_blocked = models.BooleanField("Выдача заблокирована", default=False)
    block_reason = models.CharField("Причина блокировки", max_length=200, blank=True)
    favorite_books = models.ManyToManyField(Book, verbose_name="Избранные книги", through="Favorite",
                                            related_name="fans", blank=True)

    class Meta:
        verbose_name = "Читатель"
        verbose_name_plural = "Читатели"
        ordering = ["full_name"]
        constraints = [
            models.CheckConstraint(condition=Q(is_blocked=False) | ~Q(block_reason=""),
                                   name="reader_block_reason_required"),
        ]
    def clean(self):
        if not self.is_blocked:
            self.block_reason = ""
        super().clean()

    def __str__(self):
        return f"{self.full_name} ({self.card_number})"


class Staff(models.Model):
    class Role(models.TextChoices):
        LIBRARIAN = "librarian", "Библиотекарь"
        ADMIN = "admin", "Администратор"

    user = models.OneToOneField(settings.AUTH_USER_MODEL, verbose_name="Учётная запись", on_delete=models.CASCADE,
                                related_name="staff_profile")
    full_name = models.CharField("ФИО", max_length=150)
    role = models.CharField("Роль", max_length=10, choices=Role.choices, default=Role.LIBRARIAN)
    position = models.CharField("Должность", max_length=100, blank=True)

    class Meta:
        verbose_name = "Сотрудник"
        verbose_name_plural = "Сотрудники"
        ordering = ["full_name"]

    def __str__(self):
        return f"{self.full_name} ({self.get_role_display()})"


class LibrarySettings(models.Model):
    """Единственная строка настроек (id = 1)."""

    id = models.PositiveSmallIntegerField(primary_key=True, default=1, editable=False)
    fine_per_day = models.DecimalField("Ставка штрафа за день, руб.", max_digits=6, decimal_places=2, default=5,
                                       validators=[MinValueValidator(0)])
    loan_days = models.PositiveSmallIntegerField("Срок выдачи, дней", default=14,
                                                 validators=[MinValueValidator(1), MaxValueValidator(365)])
    renewal_days = models.PositiveSmallIntegerField("Срок продления, дней", default=14,
                                                    validators=[MinValueValidator(1), MaxValueValidator(365)])
    max_renewals = models.PositiveSmallIntegerField("Число продлений", default=1,
                                                    validators=[MaxValueValidator(5)])
    reservation_hold_days = models.PositiveSmallIntegerField("Срок хранения брони, дней", default=3,
                                                             validators=[MinValueValidator(1), MaxValueValidator(30)])
    reminder_days = models.PositiveSmallIntegerField("Напоминать за, дней", default=2, validators=[MaxValueValidator(14)])
    
    class Meta:
        verbose_name = "Настройки библиотеки"
        verbose_name_plural = "Настройки библиотеки"

    def save(self, *args, **kwargs):
        self.pk = 1
        super().save(*args, **kwargs)

    @classmethod
    def get(cls):
        obj, _ = cls.objects.get_or_create(pk=1)
        return obj

    def __str__(self):
        return "Настройки библиотеки"


class Reservation(models.Model):
    class Status(models.TextChoices):
        ACTIVE = "active", "В очереди"
        READY = "ready", "Книга отложена"
        FULFILLED = "fulfilled", "Выполнена"
        EXPIRED = "expired", "Истекла"
        CANCELLED = "cancelled", "Отменена"

    reader = models.ForeignKey(Reader, verbose_name="Читатель", on_delete=models.PROTECT, related_name="reservations")
    book = models.ForeignKey(Book, verbose_name="Книга", on_delete=models.PROTECT, related_name="reservations")
    created_at = models.DateTimeField("Подана", default=timezone.now)
    status = models.CharField("Статус", max_length=10, choices=Status.choices, default=Status.ACTIVE)
    assigned_copy = models.ForeignKey(Copy, verbose_name="Закреплённый экземпляр", on_delete=models.SET_NULL,
                                      null=True, blank=True, related_name="reservations")
    ready_at = models.DateField("Отложена", null=True, blank=True)
    hold_until = models.DateField("Хранится до", null=True, blank=True)

    class Meta:
        verbose_name = "Заявка на бронирование"
        verbose_name_plural = "Заявки на бронирование"
        ordering = ["created_at", "id"]
        constraints = [
            models.UniqueConstraint(fields=["reader", "book"], condition=Q(status__in=["active", "ready"]),
                                    name="one_active_reservation_per_reader_book"),
            models.CheckConstraint(
                condition=(
                    Q(status="ready",
                      assigned_copy__isnull=False,
                      hold_until__isnull=False,
                      ready_at__isnull=False)
                    | ~Q(status="ready")
                ),
                name="reservation_ready_needs_copy"),
            models.CheckConstraint(
                condition=(Q(hold_until__isnull=True) | Q(ready_at__isnull=True) | Q(hold_until__gte=F("ready_at"))),
                name="reservation_hold_after_ready"),
        ]

    def __str__(self):
        return f"Заявка #{self.pk}: {self.reader.full_name} — {self.book}"


class Loan(models.Model):
    copy = models.ForeignKey(Copy, verbose_name="Экземпляр", on_delete=models.PROTECT, related_name="loans")
    reader = models.ForeignKey(Reader, verbose_name="Читатель", on_delete=models.PROTECT, related_name="loans")
    issued_by = models.ForeignKey(Staff, verbose_name="Выдал", on_delete=models.PROTECT, related_name="issued_loans")
    received_by = models.ForeignKey(Staff, verbose_name="Принял", on_delete=models.SET_NULL, null=True, blank=True,
                                    related_name="received_loans")
    reservation = models.ForeignKey(Reservation, verbose_name="По заявке", on_delete=models.SET_NULL,
                                    null=True, blank=True, related_name="loans")
    issued_at = models.DateField("Дата выдачи", default=timezone.localdate)
    due_date = models.DateField("Срок возврата", null=True, blank=True)
    returned_at = models.DateField("Дата возврата", null=True, blank=True)
    return_condition = models.CharField("Состояние при возврате", max_length=10, choices=Copy.Condition.choices,
                                        blank=True)

    class Meta:
        verbose_name = "Выдача"
        verbose_name_plural = "Выдачи"
        ordering = ["-issued_at", "-id"]
        constraints = [
            models.UniqueConstraint(fields=["copy"], condition=Q(returned_at__isnull=True),
                                    name="one_open_loan_per_copy"),
            models.CheckConstraint(condition=Q(due_date__gte=F("issued_at")), name="loan_due_after_issue"),
            models.CheckConstraint(condition=Q(returned_at__isnull=True) | Q(returned_at__gte=F("issued_at")),
                                   name="loan_return_after_issue"),
                                   
        ]
    def save(self, *args, **kwargs):
        if not self.due_date:
            from datetime import timedelta
            self.due_date = (self.issued_at or timezone.localdate()) + timedelta(
                days=LibrarySettings.get().loan_days
            )
        super().save(*args, **kwargs)

    @property
    def is_open(self):
        return self.returned_at is None

    def overdue_days(self, today=None):
        """Дни просрочки: фактическая дата (или сегодня для открытой выдачи) минус срок возврата."""
        end = self.returned_at or today or timezone.localdate()
        return max((end - self.due_date).days, 0)

    def __str__(self):
        return f"Выдача #{self.pk}: {self.copy.inventory_number} → {self.reader.card_number}"


class Renewal(models.Model):
    loan = models.ForeignKey(Loan, verbose_name="Выдача", on_delete=models.CASCADE, related_name="renewals")
    renewed_at = models.DateField("Дата продления", default=timezone.localdate)
    previous_due_date = models.DateField("Прежний срок возврата")
    new_due_date = models.DateField("Новый срок возврата")

    class Meta:
        verbose_name = "Продление"
        verbose_name_plural = "Продления"
        ordering = ["-renewed_at", "-id"]
        constraints = [
            models.CheckConstraint(condition=Q(new_due_date__gt=F("previous_due_date")),
                                   name="renewal_new_after_previous"),
        ]

    def __str__(self):
        return f"Продление выдачи #{self.loan_id} до {self.new_due_date:%d.%m.%Y}"


class Fine(models.Model):
    class Status(models.TextChoices):
        UNPAID = "unpaid", "Не оплачен"
        PAID = "paid", "Оплачен"

    loan = models.ForeignKey(Loan, verbose_name="Выдача", on_delete=models.PROTECT, related_name="fines")
    days_overdue = models.PositiveSmallIntegerField("Дней просрочки", validators=[MinValueValidator(1)])
    rate_per_day = models.DecimalField("Ставка за день, руб.", max_digits=6, decimal_places=2,
                                       validators=[MinValueValidator(0)])
    amount = models.DecimalField("Сумма штрафа, руб.", max_digits=8, decimal_places=2,
                                 validators=[MinValueValidator(0)])
    status = models.CharField("Статус", max_length=10, choices=Status.choices, default=Status.UNPAID)
    accrued_at = models.DateField("Дата начисления", default=timezone.localdate)
    paid_at = models.DateField("Дата оплаты", null=True, blank=True)
    accepted_by = models.ForeignKey(Staff, verbose_name="Оплату принял", on_delete=models.SET_NULL,
                                    null=True, blank=True, related_name="accepted_fines")

    class Meta:
        verbose_name = "Штраф"
        verbose_name_plural = "Штрафы"
        ordering = ["-accrued_at", "-id"]
        constraints = [
            models.CheckConstraint(condition=Q(days_overdue__gte=1), name="fine_days_min"),
            models.CheckConstraint(condition=Q(amount__gte=0), name="fine_amount_min"),
            models.CheckConstraint(
                condition=(Q(status="paid", paid_at__isnull=False) | Q(status="unpaid", paid_at__isnull=True)),
                name="fine_paid_date_consistent"),
        ]

    def __str__(self):
        return f"Штраф {self.amount} руб. по выдаче #{self.loan_id}"


class Notification(models.Model):
    class Kind(models.TextChoices):
        DUE_SOON = "due_soon", "Скоро срок возврата"
        RESERVATION_READY = "reservation_ready", "Книга отложена"
        BLOCKED = "blocked", "Выдача заблокирована"
        FINE = "fine", "Начислен штраф"
        INFO = "info", "Сообщение"

    reader = models.ForeignKey(Reader, verbose_name="Читатель", on_delete=models.CASCADE, related_name="notifications")
    kind = models.CharField("Вид", max_length=20, choices=Kind.choices, default=Kind.INFO)
    text = models.CharField("Текст", max_length=255)
    created_at = models.DateTimeField("Создано", auto_now_add=True)
    is_read = models.BooleanField("Прочитано", default=False)
    loan = models.ForeignKey(Loan, verbose_name="Выдача", on_delete=models.SET_NULL, null=True, blank=True,
                             related_name="notifications")
    reservation = models.ForeignKey(Reservation, verbose_name="Заявка", on_delete=models.SET_NULL, null=True,
                                    blank=True, related_name="notifications")
    
    class Meta:
        verbose_name = "Уведомление"
        verbose_name_plural = "Уведомления"
        ordering = ["-created_at", "-id"]
        constraints = [
            models.UniqueConstraint(
                fields=["reader", "kind", "loan"],
                condition=Q(kind="due_soon", loan__isnull=False),
                name="unique_due_soon_per_loan",
            ),
        ]
    def __str__(self):
        return f"{self.get_kind_display()}: {self.text[:40]}"


class Favorite(models.Model):
    """Связующая таблица «многие ко многим» Читатель — Книга с атрибутом added_at."""
    reader = models.ForeignKey(Reader, verbose_name="Читатель", on_delete=models.CASCADE, related_name="favorites")
    book = models.ForeignKey(Book, verbose_name="Книга", on_delete=models.CASCADE, related_name="favorites")
    added_at = models.DateTimeField("Добавлено", auto_now_add=True)

    class Meta:
        verbose_name = "Избранное"
        verbose_name_plural = "Избранное"
        ordering = ["-added_at"]
        constraints = [models.UniqueConstraint(fields=["reader", "book"], name="unique_favorite")]

    def __str__(self):
        return f"{self.reader.full_name} → {self.book}"
