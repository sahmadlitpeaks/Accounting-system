"""Statement import and payment matching.

``import_statement_csv`` ingests rows of ``date,description,amount`` (ISO date;
signed amount). ``auto_match`` pairs each unmatched line with an approved,
not-yet-reconciled payment of the same company, direction and amount within a
date tolerance — the standard first pass; leftovers are matched manually.
"""
import csv
import io
from datetime import timedelta
from decimal import Decimal

from django.db import transaction

from apps.orders.models import Payment

from .models import BankStatement, BankStatementLine

DATE_TOLERANCE_DAYS = 5


@transaction.atomic
def import_statement_csv(bank_account, content: str, statement_date, reference="") -> BankStatement:
    statement = BankStatement.objects.create(
        bank_account=bank_account, statement_date=statement_date, reference=reference,
    )
    reader = csv.reader(io.StringIO(content.strip()))
    lines = []
    for row in reader:
        if not row or row[0].strip().lower() in ("date", ""):
            continue  # header / blank
        date_str, description, amount = row[0].strip(), row[1].strip(), Decimal(row[2].strip())
        lines.append(BankStatementLine(
            statement=statement, date=date_str, description=description, amount=amount,
        ))
    BankStatementLine.objects.bulk_create(lines)
    return statement


@transaction.atomic
def auto_match(statement: BankStatement) -> dict:
    """Match unmatched lines to payments. Returns {matched, unmatched} counts."""
    company = statement.bank_account.company
    matched = 0
    for line in statement.lines.select_for_update().filter(status=BankStatementLine.Status.UNMATCHED):
        direction = Payment.Direction.INBOUND if line.amount > 0 else Payment.Direction.OUTBOUND
        candidates = Payment.objects.filter(
            company=company,
            direction=direction,
            amount=abs(line.amount),
            approval_status=Payment.Approval.APPROVED,
            date__gte=line.date - timedelta(days=DATE_TOLERANCE_DAYS),
            date__lte=line.date + timedelta(days=DATE_TOLERANCE_DAYS),
            bank_lines__isnull=True,  # not already reconciled
        ).order_by("date")
        payment = candidates.first()
        if payment:
            line.matched_payment = payment
            line.status = BankStatementLine.Status.MATCHED
            line.save(update_fields=["matched_payment", "status", "updated_at"])
            matched += 1
    return {
        "matched": matched,
        "unmatched": statement.lines.filter(status=BankStatementLine.Status.UNMATCHED).count(),
    }


def match_manually(line: BankStatementLine, payment: Payment) -> BankStatementLine:
    line.matched_payment = payment
    line.status = BankStatementLine.Status.MANUAL
    line.save(update_fields=["matched_payment", "status", "updated_at"])
    return line
