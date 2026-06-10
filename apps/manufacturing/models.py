"""Manufacturing: bills of material and work orders.

Completing a work order consumes component stock (at FIFO/avg cost) and
receives the finished product at the rolled-up component cost. Inventory value
moves within 1140, so no separate GL entry is required — valuation stays
correct and COGS flows through on the eventual sale.
"""
from decimal import Decimal

from django.db import models

from apps.core.models import Company, TimeStampedModel
from apps.masterdata.models import Item, Warehouse

ZERO = Decimal("0")


class BillOfMaterial(TimeStampedModel):
    company = models.ForeignKey(Company, on_delete=models.CASCADE, related_name="boms")
    product = models.ForeignKey(Item, on_delete=models.PROTECT, related_name="boms")
    name = models.CharField(max_length=128, blank=True)
    is_active = models.BooleanField(default=True)

    class Meta:
        unique_together = ("company", "product")

    def __str__(self):
        return self.name or f"BOM for {self.product.sku}"


class BOMLine(TimeStampedModel):
    bom = models.ForeignKey(BillOfMaterial, on_delete=models.CASCADE, related_name="lines")
    component = models.ForeignKey(Item, on_delete=models.PROTECT, related_name="+")
    quantity = models.DecimalField(max_digits=18, decimal_places=4)  # per unit of product

    def __str__(self):
        return f"{self.quantity} x {self.component.sku}"


class WorkOrder(TimeStampedModel):
    class Status(models.TextChoices):
        DRAFT = "draft", "Draft"
        DONE = "done", "Done"
        CANCELLED = "cancelled", "Cancelled"

    company = models.ForeignKey(Company, on_delete=models.CASCADE, related_name="work_orders")
    bom = models.ForeignKey(BillOfMaterial, on_delete=models.PROTECT, related_name="work_orders")
    warehouse = models.ForeignKey(Warehouse, on_delete=models.PROTECT, related_name="+")
    quantity = models.DecimalField(max_digits=18, decimal_places=4)
    date = models.DateField()
    status = models.CharField(max_length=10, choices=Status.choices, default=Status.DRAFT)
    produced_cost = models.DecimalField(max_digits=18, decimal_places=2, default=ZERO)

    class Meta:
        ordering = ["-date", "-id"]

    def __str__(self):
        return f"WO#{self.pk} {self.quantity} x {self.bom.product.sku}"
