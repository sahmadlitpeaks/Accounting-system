"""Opening balances: bring an existing business onto the system.

Posts one balanced opening journal entry from (account_code, debit, credit)
rows — the closing trial balance of the previous system. Inventory value should
arrive as the 1140 balance here, with quantities loaded separately via
``load_opening_stock`` (which books no GL of its own to avoid double counting).
"""
from decimal import Decimal

from django.db import transaction

from .services import EntryInput, LineInput, PostingError, get_account, post_entry

ZERO = Decimal("0")


@transaction.atomic
def load_opening_balances(company, as_of, rows) -> object:
    """``rows``: iterable of (account_code, debit, credit). Must balance."""
    lines = []
    total_debit = ZERO
    total_credit = ZERO
    for code, debit, credit in rows:
        debit, credit = Decimal(debit or 0), Decimal(credit or 0)
        if debit == ZERO and credit == ZERO:
            continue
        lines.append(LineInput(account=get_account(company, str(code)),
                               debit=debit, credit=credit,
                               description="Opening balance"))
        total_debit += debit
        total_credit += credit
    if total_debit != total_credit:
        raise PostingError(
            f"Opening balances do not balance: debit {total_debit} != credit {total_credit}."
        )
    return post_entry(EntryInput(
        company=company, date=as_of, memo=f"Opening balances as of {as_of}",
        source_type="opening_balance", source_id=str(as_of), lines=lines,
    ))


@transaction.atomic
def load_opening_stock(company, warehouse, as_of, rows):
    """``rows``: iterable of (item, quantity, unit_cost). Creates stock moves and
    valuation layers WITHOUT posting GL (the value belongs to the 1140 opening
    balance row). Returns the created moves."""
    from apps.inventory.models import StockMove, StockValuationLayer

    moves = []
    for item, quantity, unit_cost in rows:
        quantity, unit_cost = Decimal(quantity), Decimal(unit_cost)
        value = (quantity * unit_cost).quantize(Decimal("0.01"))
        move = StockMove.objects.create(
            company=company, item=item, warehouse=warehouse, date=as_of,
            quantity=quantity, unit_cost=unit_cost, value=value,
            source_type="opening_stock", source_id=str(as_of),
        )
        StockValuationLayer.objects.create(
            company=company, item=item, warehouse=warehouse,
            original_qty=quantity, remaining_qty=quantity,
            unit_cost=unit_cost, remaining_value=value, source_move=move,
        )
        moves.append(move)
    return moves
