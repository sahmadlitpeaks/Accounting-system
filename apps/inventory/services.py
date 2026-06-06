"""Inventory valuation service.

Supports FIFO and moving-average costing. Receipts add cost layers; issues
consume them and return the COGS so the orders module can post the GL entry.
Quantities are tracked via StockMove; costs via StockValuationLayer.
"""
from decimal import Decimal

from django.db import transaction
from django.db.models import Sum

from apps.masterdata.models import Item

from .models import ZERO, StockMove, StockValuationLayer


class InventoryError(Exception):
    pass


def _q2(value: Decimal) -> Decimal:
    return Decimal(value).quantize(Decimal("0.01"))


def stock_on_hand(item, warehouse=None) -> Decimal:
    qs = StockMove.objects.filter(item=item)
    if warehouse:
        qs = qs.filter(warehouse=warehouse)
    return qs.aggregate(q=Sum("quantity"))["q"] or ZERO


def stock_value(item, warehouse=None) -> Decimal:
    qs = StockValuationLayer.objects.filter(item=item, remaining_qty__gt=0)
    if warehouse:
        qs = qs.filter(warehouse=warehouse)
    return qs.aggregate(v=Sum("remaining_value"))["v"] or ZERO


@transaction.atomic
def receive_stock(*, company, item, warehouse, quantity, unit_cost, date, source_type="", source_id="") -> StockMove:
    """Record an inbound movement and add/refresh the cost layer(s)."""
    if quantity <= 0:
        raise InventoryError("Receipt quantity must be positive.")
    unit_cost = Decimal(unit_cost)
    value = _q2(Decimal(quantity) * unit_cost)
    move = StockMove.objects.create(
        company=company, item=item, warehouse=warehouse, date=date,
        quantity=Decimal(quantity), unit_cost=unit_cost, value=value,
        source_type=source_type, source_id=str(source_id),
    )

    if item.valuation_method == Item.Valuation.MOVING_AVERAGE:
        pool = (
            StockValuationLayer.objects.select_for_update()
            .filter(item=item, warehouse=warehouse, remaining_qty__gt=0)
            .first()
        )
        if pool:
            pool.remaining_qty += Decimal(quantity)
            pool.original_qty += Decimal(quantity)
            pool.remaining_value = _q2(pool.remaining_value + value)
            pool.unit_cost = (pool.remaining_value / pool.remaining_qty).quantize(Decimal("0.0001"))
            pool.save()
        else:
            StockValuationLayer.objects.create(
                company=company, item=item, warehouse=warehouse,
                original_qty=Decimal(quantity), remaining_qty=Decimal(quantity),
                unit_cost=unit_cost, remaining_value=value, source_move=move,
            )
    else:  # FIFO
        StockValuationLayer.objects.create(
            company=company, item=item, warehouse=warehouse,
            original_qty=Decimal(quantity), remaining_qty=Decimal(quantity),
            unit_cost=unit_cost, remaining_value=value, source_move=move,
        )
    return move


@transaction.atomic
def issue_stock(*, company, item, warehouse, quantity, date, source_type="", source_id="") -> tuple:
    """Record an outbound movement, consuming cost layers. Returns (move, cogs)."""
    quantity = Decimal(quantity)
    if quantity <= 0:
        raise InventoryError("Issue quantity must be positive.")
    available = stock_on_hand(item, warehouse)
    if quantity > available:
        raise InventoryError(
            f"Insufficient stock for {item.sku}: need {quantity}, have {available}."
        )

    layers = list(
        StockValuationLayer.objects.select_for_update()
        .filter(item=item, warehouse=warehouse, remaining_qty__gt=0)
        .order_by("created_at", "id")  # FIFO order; for avg there is one pool
    )
    remaining = quantity
    cogs = ZERO
    for layer in layers:
        if remaining <= 0:
            break
        take = min(layer.remaining_qty, remaining)
        line_cost = _q2(take * layer.unit_cost)
        cogs += line_cost
        layer.remaining_qty -= take
        layer.remaining_value = _q2(layer.remaining_value - line_cost)
        layer.save()
        remaining -= take

    cogs = _q2(cogs)
    move = StockMove.objects.create(
        company=company, item=item, warehouse=warehouse, date=date,
        quantity=-quantity,
        unit_cost=(cogs / quantity).quantize(Decimal("0.0001")) if quantity else ZERO,
        value=-cogs, source_type=source_type, source_id=str(source_id),
    )
    return move, cogs
