"""Period locking and year-end closing.

* ``close_period`` locks a period so nothing can post into it (the posting
  service already rejects closed periods).
* ``close_year`` posts a closing entry that zeroes every Income and Expense
  account into Retained Earnings (3200) — the temporary accounts reset and the
  net result becomes permanent equity.
"""
from decimal import Decimal

from django.db import transaction
from django.db.models import Sum

from .models import (
    AccountType,
    AccountingPeriod,
    JournalEntry,
    JournalLine,
)
from .services import EntryInput, LineInput, PostingError, get_account, post_entry

ZERO = Decimal("0")


def close_period(period: AccountingPeriod) -> AccountingPeriod:
    if period.status == AccountingPeriod.Status.CLOSED:
        raise PostingError(f"Period {period.name} is already closed.")
    period.status = AccountingPeriod.Status.CLOSED
    period.save(update_fields=["status", "updated_at"])
    return period


def reopen_period(period: AccountingPeriod) -> AccountingPeriod:
    period.status = AccountingPeriod.Status.OPEN
    period.save(update_fields=["status", "updated_at"])
    return period


def _net_by_account(company, types, start, end):
    rows = (
        JournalLine.objects.filter(
            entry__company=company,
            entry__status=JournalEntry.Status.POSTED,
            account__type__in=types,
            entry__date__gte=start,
            entry__date__lte=end,
        )
        .values("account_id", "account__code")
        .annotate(debit=Sum("base_debit"), credit=Sum("base_credit"))
    )
    result = []
    for r in rows:
        net = (r["debit"] or ZERO) - (r["credit"] or ZERO)  # debit-positive
        if net != ZERO:
            result.append((r["account_id"], net))
    return result


@transaction.atomic
def close_year(company, start_date, end_date, retained_earnings_code="3200") -> JournalEntry:
    """Post the year-end closing entry zeroing Income & Expense into retained
    earnings. Returns the closing journal entry (or None if nothing to close)."""
    from .models import Account

    lines = []
    pnl_net = ZERO  # debit-positive total of income+expense nets

    for account_id, net in _net_by_account(company, [AccountType.INCOME, AccountType.EXPENSE], start_date, end_date):
        account = Account.objects.get(pk=account_id)
        pnl_net += net
        # Zero the account: post the opposite side of its current net balance.
        if net > 0:
            lines.append(LineInput(account=account, credit=net))
        else:
            lines.append(LineInput(account=account, debit=-net))

    if not lines:
        return None

    # Income net is credit-heavy (negative debit-total); expense net is positive.
    # Net profit = -(income+expense debit-total) ... reconcile via retained earnings.
    retained = get_account(company, retained_earnings_code)
    # pnl_net (debit-positive) > 0 means expenses exceeded income -> a loss.
    if pnl_net > 0:  # loss: debit retained earnings (reduce equity)
        lines.append(LineInput(account=retained, debit=pnl_net))
    else:            # profit: credit retained earnings (increase equity)
        lines.append(LineInput(account=retained, credit=-pnl_net))

    return post_entry(EntryInput(
        company=company, date=end_date,
        memo=f"Year-end close {start_date}..{end_date}",
        source_type="year_close", source_id=str(end_date),
        lines=lines,
    ))
