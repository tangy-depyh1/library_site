from datetime import timedelta

from django.core.management.base import BaseCommand, CommandError
from django.utils import timezone
from django.utils.dateparse import parse_date

from library.models import LibrarySettings, Loan, Notification


class Command(BaseCommand):
    help = "Create cabinet notifications for loans approaching their due date."

    def add_arguments(self, parser):
        parser.add_argument(
            "--today",
            help="Reference date in YYYY-MM-DD format (defaults to the local date).",
        )

    def handle(self, *args, **options):
        today_arg = options["today"]
        today = parse_date(today_arg) if today_arg else timezone.localdate()
        if today is None:
            raise CommandError("--today must use YYYY-MM-DD format.")

        reminder_days = LibrarySettings.get().reminder_days
        due_through = today + timedelta(days=reminder_days)
        loans = Loan.objects.filter(
            returned_at__isnull=True,
            due_date__gte=today,
            due_date__lte=due_through,
        ).select_related("reader", "copy__book")

        created_count = 0
        for loan in loans:
            text = (
                f"Срок возврата книги «{loan.copy.book.title}» — "
                f"{loan.due_date:%d.%m.%Y}."
            )
            _, created = Notification.objects.get_or_create(
                loan=loan,
                kind=Notification.Kind.DUE_SOON,
                defaults={"reader": loan.reader, "text": text},
            )
            created_count += int(created)

        self.stdout.write(
            self.style.SUCCESS(f"Created {created_count} due-date reminder(s).")
        )
