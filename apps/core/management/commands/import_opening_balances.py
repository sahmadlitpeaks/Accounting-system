"""Import opening balances from a CSV of account_code,debit,credit.

    python manage.py import_opening_balances balances.csv --company 1 --date 2026-01-01
"""
import csv
from datetime import date

from django.core.management.base import BaseCommand, CommandError

from apps.accounting.opening import load_opening_balances
from apps.accounting.services import PostingError
from apps.core.models import Company


class Command(BaseCommand):
    help = "Post an opening-balance journal entry from a CSV (account_code,debit,credit)."

    def add_arguments(self, parser):
        parser.add_argument("csv_path")
        parser.add_argument("--company", type=int, required=True)
        parser.add_argument("--date", default=str(date.today()))

    def handle(self, *args, **options):
        company = Company.objects.get(pk=options["company"])
        rows = []
        with open(options["csv_path"], newline="") as fh:
            for row in csv.reader(fh):
                if not row or row[0].strip().lower() in ("account_code", "code", ""):
                    continue
                rows.append((row[0].strip(), row[1].strip() or 0, row[2].strip() or 0))
        try:
            entry = load_opening_balances(company, options["date"], rows)
        except PostingError as exc:
            raise CommandError(str(exc)) from exc
        self.stdout.write(self.style.SUCCESS(
            f"Posted opening entry JE#{entry.pk} with {entry.lines.count()} lines."
        ))
