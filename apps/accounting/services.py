"""Posting service: the only sanctioned way to write to the ledger.

Guarantees the core invariant ``Σ base_debit == Σ base_credit`` and that posted
entries are balanced, single-company, hit only postable accounts, and land in an
open period. Posting is atomic.
"""
from dataclasses import dataclass, field
from decimal import Decimal
from typing import Optional

from django.db import transaction

from apps.core.models import Currency

from .models import (
    ZERO,
    Account,
    AccountingPeriod,
    JournalEntry,
    JournalLine,
)


class PostingError(Exception):
    """Raised when a journal entry cannot be posted."""


def get_account(company, code: str) -> Account:
    """Resolve a postable account by code within a company."""
    try:
        return Account.objects.get(company=company, code=code)
    except Account.DoesNotExist as exc:
        raise PostingError(f"Account {code} not found for company {company.id}.") from exc


@dataclass
class LineInput:
    account: Account
    debit: Decimal = ZERO
    credit: Decimal = ZERO
    currency: Optional[Currency] = None
    fx_rate: Decimal = Decimal("1")
    description: str = ""
    party: object = None


@dataclass
class EntryInput:
    company: object
    date: object
    lines: list = field(default_factory=list)
    memo: str = ""
    reference: str = ""
    source_type: str = ""
    source_id: str = ""
    reversal_of: object = None


def _q(value: Decimal) -> Decimal:
    return Decimal(value).quantize(Decimal("0.01"))


def _resolve_period(company, on_date) -> Optional[AccountingPeriod]:
    period = (
        AccountingPeriod.objects.filter(
            company=company, start_date__lte=on_date, end_date__gte=on_date
        ).first()
    )
    if period and period.status == AccountingPeriod.Status.CLOSED:
        raise PostingError(f"Period {period.name} is closed; cannot post on {on_date}.")
    return period


@transaction.atomic
def post_entry(data: EntryInput) -> JournalEntry:
    """Create and post a balanced journal entry. Returns the posted entry."""
    if len(data.lines) < 2:
        raise PostingError("A journal entry needs at least two lines.")

    base_currency = data.company.base_currency
    period = _resolve_period(data.company, data.date)

    total_debit = ZERO
    total_credit = ZERO
    prepared = []
    for li in data.lines:
        if li.account.company_id != data.company.id:
            raise PostingError(f"Account {li.account.code} belongs to another company.")
        if li.account.is_group:
            raise PostingError(f"Account {li.account.code} is a group account; not postable.")
        if li.debit < ZERO or li.credit < ZERO:
            raise PostingError("Debit/credit must be non-negative.")
        if (li.debit > ZERO) == (li.credit > ZERO):
            raise PostingError("Each line must have exactly one of debit or credit.")

        currency = li.currency or base_currency
        rate = li.fx_rate if currency.code != base_currency.code else Decimal("1")
        base_debit = _q(li.debit * rate)
        base_credit = _q(li.credit * rate)
        total_debit += base_debit
        total_credit += base_credit
        prepared.append((li, currency, rate, base_debit, base_credit))

    if total_debit != total_credit:
        raise PostingError(
            f"Entry not balanced: debit {total_debit} != credit {total_credit}."
        )

    entry = JournalEntry.objects.create(
        company=data.company,
        date=data.date,
        period=period,
        reference=data.reference,
        memo=data.memo,
        source_type=data.source_type,
        source_id=str(data.source_id),
        status=JournalEntry.Status.POSTED,
        reversal_of=data.reversal_of,
    )
    JournalLine.objects.bulk_create(
        [
            JournalLine(
                entry=entry,
                account=li.account,
                description=li.description,
                currency=currency,
                fx_rate=rate,
                debit=_q(li.debit),
                credit=_q(li.credit),
                base_debit=base_debit,
                base_credit=base_credit,
                party=li.party,
            )
            for (li, currency, rate, base_debit, base_credit) in prepared
        ]
    )
    return entry


@transaction.atomic
def reverse_entry(entry: JournalEntry, on_date=None, memo: str = "") -> JournalEntry:
    """Post a mirror-image entry that cancels ``entry`` (debits<->credits)."""
    if entry.status != JournalEntry.Status.POSTED:
        raise PostingError("Only posted entries can be reversed.")
    lines = [
        LineInput(
            account=line.account,
            debit=line.credit,
            credit=line.debit,
            currency=line.currency,
            fx_rate=line.fx_rate,
            description=f"Reversal: {line.description}",
            party=line.party,
        )
        for line in entry.lines.all()
    ]
    return post_entry(
        EntryInput(
            company=entry.company,
            date=on_date or entry.date,
            lines=lines,
            memo=memo or f"Reversal of JE#{entry.pk}",
            source_type=entry.source_type,
            source_id=entry.source_id,
            reversal_of=entry,
        )
    )


def trial_balance(company, as_of=None) -> list:
    """Return per-account debit/credit/balance totals for posted entries."""
    from django.db.models import Sum

    qs = JournalLine.objects.filter(
        entry__company=company, entry__status=JournalEntry.Status.POSTED
    )
    if as_of:
        qs = qs.filter(entry__date__lte=as_of)
    rows = (
        qs.values("account__code", "account__name", "account__type")
        .annotate(debit=Sum("base_debit"), credit=Sum("base_credit"))
        .order_by("account__code")
    )
    result = []
    for r in rows:
        debit = r["debit"] or ZERO
        credit = r["credit"] or ZERO
        result.append(
            {
                "code": r["account__code"],
                "name": r["account__name"],
                "type": r["account__type"],
                "debit": debit,
                "credit": credit,
                "balance": debit - credit,
            }
        )
    return result
