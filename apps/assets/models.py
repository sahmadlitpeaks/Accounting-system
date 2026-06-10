"""Fixed assets with straight-line depreciation.

Acquisition capitalises cost to PP&E (1510); each monthly run posts
Dr 5300 Depreciation Expense / Cr 1520 Accumulated Depreciation; disposal
clears cost and accumulated depreciation, with the difference vs proceeds
going to FX-neutral gain (4900) / loss (5900).
"""
from decimal import Decimal

from django.db import models

from apps.core.models import Company, TimeStampedModel

ZERO = Decimal("0")


class AssetCategory(TimeStampedModel):
    company = models.ForeignKey(Company, on_delete=models.CASCADE, related_name="asset_categories")
    name = models.CharField(max_length=64)
    useful_life_months = models.PositiveSmallIntegerField(default=60)
    asset_account_code = models.CharField(max_length=20, default="1510")
    accum_depreciation_code = models.CharField(max_length=20, default="1520")
    expense_account_code = models.CharField(max_length=20, default="5300")

    class Meta:
        unique_together = ("company", "name")
        verbose_name_plural = "asset categories"

    def __str__(self):
        return self.name


class FixedAsset(TimeStampedModel):
    class Status(models.TextChoices):
        ACTIVE = "active", "Active"
        DISPOSED = "disposed", "Disposed"

    company = models.ForeignKey(Company, on_delete=models.CASCADE, related_name="fixed_assets")
    category = models.ForeignKey(AssetCategory, on_delete=models.PROTECT, related_name="assets")
    name = models.CharField(max_length=128)
    acquisition_date = models.DateField()
    cost = models.DecimalField(max_digits=18, decimal_places=2)
    salvage_value = models.DecimalField(max_digits=18, decimal_places=2, default=ZERO)
    useful_life_months = models.PositiveSmallIntegerField()
    accumulated_depreciation = models.DecimalField(max_digits=18, decimal_places=2, default=ZERO)
    status = models.CharField(max_length=10, choices=Status.choices, default=Status.ACTIVE)
    acquisition_entry = models.ForeignKey(
        "accounting.JournalEntry", null=True, blank=True, on_delete=models.SET_NULL, related_name="+"
    )

    class Meta:
        ordering = ["company", "name"]

    def __str__(self):
        return self.name

    @property
    def depreciable_base(self) -> Decimal:
        return self.cost - self.salvage_value

    @property
    def monthly_depreciation(self) -> Decimal:
        if self.useful_life_months == 0:
            return ZERO
        return (self.depreciable_base / self.useful_life_months).quantize(Decimal("0.01"))

    @property
    def book_value(self) -> Decimal:
        return self.cost - self.accumulated_depreciation

    @property
    def remaining_depreciable(self) -> Decimal:
        return self.depreciable_base - self.accumulated_depreciation


class DepreciationEntry(TimeStampedModel):
    """One asset-month of depreciation; the (asset, period) uniqueness makes
    depreciation runs idempotent."""

    asset = models.ForeignKey(FixedAsset, on_delete=models.CASCADE, related_name="depreciation_entries")
    period = models.CharField(max_length=7)  # YYYY-MM
    amount = models.DecimalField(max_digits=18, decimal_places=2)
    journal_entry = models.ForeignKey(
        "accounting.JournalEntry", null=True, blank=True, on_delete=models.SET_NULL, related_name="+"
    )

    class Meta:
        unique_together = ("asset", "period")
        ordering = ["period"]
        verbose_name_plural = "depreciation entries"

    def __str__(self):
        return f"{self.asset.name} {self.period}: {self.amount}"
