"""Master data: trading partners, items, warehouses, tax codes, price lists."""
from decimal import Decimal

from django.db import models

from apps.core.models import Company, Currency, TimeStampedModel


class Party(TimeStampedModel):
    """A customer and/or supplier. A single party can be both."""

    company = models.ForeignKey(Company, on_delete=models.CASCADE, related_name="parties")
    name = models.CharField(max_length=128)
    is_customer = models.BooleanField(default=False)
    is_supplier = models.BooleanField(default=False)
    tax_registration_number = models.CharField(max_length=32, blank=True)
    country = models.CharField(max_length=2, blank=True)
    currency = models.ForeignKey(Currency, null=True, blank=True, on_delete=models.PROTECT, related_name="+")
    email = models.EmailField(blank=True)
    phone = models.CharField(max_length=32, blank=True)
    address = models.TextField(blank=True)
    payment_terms_days = models.PositiveSmallIntegerField(default=0)

    class Meta:
        verbose_name_plural = "parties"
        ordering = ["name"]

    def __str__(self):
        return self.name


class UnitOfMeasure(TimeStampedModel):
    company = models.ForeignKey(Company, on_delete=models.CASCADE, related_name="uoms")
    code = models.CharField(max_length=16)  # PCS, KG, BOX
    name = models.CharField(max_length=64)

    class Meta:
        unique_together = ("company", "code")
        ordering = ["code"]

    def __str__(self):
        return self.code


class TaxCode(TimeStampedModel):
    """A tax rate and how it posts. ``kind`` distinguishes VAT/sales/withholding."""

    class Kind(models.TextChoices):
        VAT = "vat", "VAT"
        SALES = "sales", "Sales Tax"
        WITHHOLDING = "wht", "Withholding Tax"
        EXEMPT = "exempt", "Exempt"
        ZERO = "zero", "Zero-rated"

    company = models.ForeignKey(Company, on_delete=models.CASCADE, related_name="tax_codes")
    name = models.CharField(max_length=64)  # "UAE VAT 5%", "PK GST 18%"
    kind = models.CharField(max_length=8, choices=Kind.choices)
    rate = models.DecimalField(max_digits=6, decimal_places=3, default=Decimal("0"))  # percent
    # Where the tax posts.
    output_account = models.ForeignKey(
        "accounting.Account", null=True, blank=True, on_delete=models.PROTECT, related_name="+"
    )
    input_account = models.ForeignKey(
        "accounting.Account", null=True, blank=True, on_delete=models.PROTECT, related_name="+"
    )
    is_active = models.BooleanField(default=True)

    class Meta:
        unique_together = ("company", "name")
        ordering = ["name"]

    def __str__(self):
        return f"{self.name} ({self.rate}%)"


class Item(TimeStampedModel):
    """A product or service. Stock items participate in inventory valuation."""

    class Kind(models.TextChoices):
        STOCK = "stock", "Stock"
        SERVICE = "service", "Service"

    class Valuation(models.TextChoices):
        FIFO = "fifo", "FIFO"
        MOVING_AVERAGE = "moving_average", "Moving Average"

    company = models.ForeignKey(Company, on_delete=models.CASCADE, related_name="items")
    sku = models.CharField(max_length=64)
    name = models.CharField(max_length=128)
    kind = models.CharField(max_length=8, choices=Kind.choices, default=Kind.STOCK)
    uom = models.ForeignKey(UnitOfMeasure, on_delete=models.PROTECT, related_name="items")
    valuation_method = models.CharField(
        max_length=16, choices=Valuation.choices, default=Valuation.MOVING_AVERAGE
    )
    sales_tax_code = models.ForeignKey(
        TaxCode, null=True, blank=True, on_delete=models.PROTECT, related_name="+"
    )
    # HSN (goods) / SAC (services) classification code used on tax invoices.
    hsn_sac_code = models.CharField(max_length=16, blank=True)
    standard_cost = models.DecimalField(max_digits=18, decimal_places=4, default=Decimal("0"))
    sales_price = models.DecimalField(max_digits=18, decimal_places=4, default=Decimal("0"))
    is_active = models.BooleanField(default=True)

    class Meta:
        unique_together = ("company", "sku")
        ordering = ["sku"]

    def __str__(self):
        return f"{self.sku} {self.name}"


class Warehouse(TimeStampedModel):
    company = models.ForeignKey(Company, on_delete=models.CASCADE, related_name="warehouses")
    code = models.CharField(max_length=16)
    name = models.CharField(max_length=64)
    address = models.TextField(blank=True)

    class Meta:
        unique_together = ("company", "code")
        ordering = ["code"]

    def __str__(self):
        return f"{self.code} {self.name}"


class PriceList(TimeStampedModel):
    company = models.ForeignKey(Company, on_delete=models.CASCADE, related_name="price_lists")
    name = models.CharField(max_length=64)
    currency = models.ForeignKey(Currency, on_delete=models.PROTECT, related_name="+")

    class Meta:
        unique_together = ("company", "name")

    def __str__(self):
        return self.name


class PriceListItem(TimeStampedModel):
    price_list = models.ForeignKey(PriceList, on_delete=models.CASCADE, related_name="items")
    item = models.ForeignKey(Item, on_delete=models.CASCADE, related_name="prices")
    price = models.DecimalField(max_digits=18, decimal_places=4)

    class Meta:
        unique_together = ("price_list", "item")

    def __str__(self):
        return f"{self.item.sku} @ {self.price}"
