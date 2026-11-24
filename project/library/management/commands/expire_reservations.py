from django.core.management.base import BaseCommand

from library.reader_workflow_views import expire_ready_reservations


class Command(BaseCommand):
    help = "Expire ready reservations whose hold period has ended."

    def handle(self, *args, **options):
        expired = expire_ready_reservations()
        self.stdout.write(self.style.SUCCESS(f"Expired {expired} reservation(s)."))
