from django.contrib import admin

from . import models as m


class BookAuthorInline(admin.TabularInline):
    model = m.BookAuthor
    extra = 1


@admin.register(m.Genre)
class GenreAdmin(admin.ModelAdmin):
    search_fields = ["name"]


@admin.register(m.Author)
class AuthorAdmin(admin.ModelAdmin):
    list_display = ["last_name", "first_name", "middle_name", "birth_year"]
    search_fields = ["last_name", "first_name"]


@admin.register(m.Book)
class BookAdmin(admin.ModelAdmin):
    list_display = ["title", "genre", "publisher", "year_published"]
    list_filter = ["genre"]
    search_fields = ["title", "isbn"]
    inlines = [BookAuthorInline]


@admin.register(m.Copy)
class CopyAdmin(admin.ModelAdmin):
    list_display = ["inventory_number", "book", "status", "condition", "shelf_location"]
    list_filter = ["status", "condition"]
    search_fields = ["inventory_number", "book__title"]


@admin.register(m.Reader)
class ReaderAdmin(admin.ModelAdmin):
    list_display = ["card_number", "full_name", "group_name", "is_blocked", "block_reason"]
    list_filter = ["is_blocked", "group_name"]
    search_fields = ["card_number", "full_name"]


@admin.register(m.Staff)
class StaffAdmin(admin.ModelAdmin):
    list_display = ["full_name", "role", "position"]


@admin.register(m.LibrarySettings)
class LibrarySettingsAdmin(admin.ModelAdmin):
    list_display = ["fine_per_day", "loan_days", "renewal_days", "max_renewals", "reservation_hold_days", "reminder_days"]


@admin.register(m.Reservation)
class ReservationAdmin(admin.ModelAdmin):
    list_display = ["id", "reader", "book", "status", "created_at", "hold_until"]
    list_filter = ["status"]


@admin.register(m.Loan)
class LoanAdmin(admin.ModelAdmin):
    list_display = ["id", "copy", "reader", "issued_at", "due_date", "returned_at"]
    list_filter = ["issued_at"]
    search_fields = ["reader__full_name", "copy__inventory_number"]


@admin.register(m.Renewal)
class RenewalAdmin(admin.ModelAdmin):
    list_display = ["loan", "renewed_at", "previous_due_date", "new_due_date"]


@admin.register(m.Fine)
class FineAdmin(admin.ModelAdmin):
    list_display = ["loan", "days_overdue", "amount", "status", "accrued_at", "paid_at"]
    list_filter = ["status"]


@admin.register(m.Notification)
class NotificationAdmin(admin.ModelAdmin):
    list_display = ["reader", "kind", "text", "created_at", "is_read"]
    list_filter = ["kind", "is_read"]


@admin.register(m.Favorite)
class FavoriteAdmin(admin.ModelAdmin):
    list_display = ["reader", "book", "added_at"]
