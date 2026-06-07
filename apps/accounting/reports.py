"""Financial statements derived from posted journal lines.

Because each account carries one of the five types, the statements are simple
aggregations:
  * P&L         = Income (credit-debit) - Expense (debit-credit)
  * Balance Sheet = Assets (debit-credit) vs Liabilities + Equity (credit-debit)
                    + current-period net profit (unallocated retained earnings)
"""
from decimal import Decimal

from django.db.models import Sum

from .models import AccountType, JournalEntry, JournalLine

ZERO = Decimal("0")


def _aggregate(company, types, as_of=None, start=None):
    """Return [(code, name, signed_balance)] for the given account types.

    ``signed_balance`` is presented in the natural sign for the statement:
    debit-positive for assets/expenses, credit-positive for the rest.
    """
    qs = JournalLine.objects.filter(
        entry__company=company,
        entry__status=JournalEntry.Status.POSTED,
        account__type__in=types,
    )
    if start:
        qs = qs.filter(entry__date__gte=start)
    if as_of:
        qs = qs.filter(entry__date__lte=as_of)
    rows = (
        qs.values("account__code", "account__name", "account__type")
        .annotate(debit=Sum("base_debit"), credit=Sum("base_credit"))
        .order_by("account__code")
    )
    out = []
    for r in rows:
        debit = r["debit"] or ZERO
        credit = r["credit"] or ZERO
        if r["account__type"] in (AccountType.ASSET, AccountType.EXPENSE):
            balance = debit - credit
        else:
            balance = credit - debit
        if balance != ZERO:
            out.append({"code": r["account__code"], "name": r["account__name"], "amount": balance})
    return out


def profit_and_loss(company, start=None, end=None) -> dict:
    income = _aggregate(company, [AccountType.INCOME], as_of=end, start=start)
    expense = _aggregate(company, [AccountType.EXPENSE], as_of=end, start=start)
    total_income = sum((r["amount"] for r in income), ZERO)
    total_expense = sum((r["amount"] for r in expense), ZERO)
    return {
        "company": company.id,
        "period": {"start": start, "end": end},
        "income": income,
        "expenses": expense,
        "total_income": total_income,
        "total_expense": total_expense,
        "net_profit": total_income - total_expense,
    }


def net_profit(company, as_of=None, start=None) -> Decimal:
    pnl = profit_and_loss(company, start=start, end=as_of)
    return pnl["net_profit"]


def balance_sheet(company, as_of=None) -> dict:
    assets = _aggregate(company, [AccountType.ASSET], as_of=as_of)
    liabilities = _aggregate(company, [AccountType.LIABILITY], as_of=as_of)
    equity = _aggregate(company, [AccountType.EQUITY], as_of=as_of)

    total_assets = sum((r["amount"] for r in assets), ZERO)
    total_liabilities = sum((r["amount"] for r in liabilities), ZERO)
    total_equity = sum((r["amount"] for r in equity), ZERO)
    # Current-period result not yet closed into retained earnings.
    current_result = net_profit(company, as_of=as_of)

    total_equity_and_liabilities = total_liabilities + total_equity + current_result
    return {
        "company": company.id,
        "as_of": as_of,
        "assets": assets,
        "liabilities": liabilities,
        "equity": equity,
        "current_year_result": current_result,
        "total_assets": total_assets,
        "total_liabilities": total_liabilities,
        "total_equity": total_equity,
        "total_equity_and_liabilities": total_equity_and_liabilities,
        "balances": total_assets == total_equity_and_liabilities,
    }
