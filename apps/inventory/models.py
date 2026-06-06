"""Inventory: stock movements and cost valuation layers."""
from decimal import Decimal

from django.db import models

from apps.core.models import Company, TimeStampedModel
from apps.masterdata.models import Item, Warehouse

ZERO = Decimal("0")


class StockMove(TimeStampedModel):
    """A signed quantity movement of an item in/out of a warehouse.
    Positive ``quantity`` = receipt, negative = issue."""

    company = models.ForeignKey(Company, on_delete=models.CASCADE, related_name="stock_moves")
    item = models.ForeignKey(Item, on_delete=models.PROTECT, related_name="stock_moves")
    warehouse = models.ForeignKey(Warehouse, on_delete=models.PROTECT, related_name="stock_moves")
    date = models.DateField()
    quantity = models.DecimalField(max_digits=18, decimal_places=4)
    unit_cost = models.DecimalField(max_digits=18, decimal_places=4, default=ZERO)
    # Total cost value of this move (qty*cost for receipts, COGS for issues).
    value = models.DecimalField(max_digits=18, decimal_places=2, default=ZERO)
    source_type = models.CharField(max_length=40, blank=True)
    source_id = models.CharField(max_length=40, blank=True)

    class Meta:
        ordering = ["date", "id"]

    def __str__(self):
        return f"{self.item.sku} {self.quantity} @ {self.warehouse.code}"


class StockValuationLayer(TimeStampedModel):
    """A cost layer consumed during issues. For FIFO items each receipt creates
    a layer; for moving-average items a single pool layer per (item, warehouse)
    is maintained and re-averaged on each receipt."""

    company = models.ForeignKey(Company, on_delete=models.CASCADE, related_name="valuation_layers")
    item = models.ForeignKey(Item, on_delete=models.PROTECT, related_name="valuation_layers")
    warehouse = models.ForeignKey(Warehouse, on_delete=models.PROTECT, related_name="valuation_layers")
    original_qty = models.DecimalField(max_digits=18, decimal_places=4)
    remaining_qty = models.DecimalField(max_digits=18, decimal_places=4)
    unit_cost = models.DecimalField(max_digits=18, decimal_places=4)
    remaining_value = models.DecimalField(max_digits=18, decimal_places=2)
    source_move = models.ForeignKey(
        StockMove, null=True, blank=True, on_delete=models.SET_NULL, related_name="+"
    )

    class Meta:
        ordering = ["created_at", "id"]

    def __str__(self):
        return f"{self.item.sku} rem {self.remaining_qty} @ {self.unit_cost}"
