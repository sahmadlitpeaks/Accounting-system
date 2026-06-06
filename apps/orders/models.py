"""Order-to-cash and procure-to-pay documents.

Sales:    SalesOrder -> Delivery (stock issue + COGS) -> CustomerInvoice (AR/rev/tax + e-invoice)
Purchase: PurchaseOrder -> GoodsReceipt (stock in) -> SupplierBill (AP/expense/input tax)
Settlement: Payment (cash/bank vs AR/AP)
"""
from decimal import Decimal

from django.db import models

from apps.core.models import Company, Currency, TimeStampedModel
from apps.masterdata.models import Item, Party, TaxCode, Warehouse

ZERO = Decimal("0")


class DocumentStatus(models.TextChoices):
    DRAFT = "draft", "Draft"
    CONFIRMED = "confirmed", "Confirmed"
    DELIVERED = "delivered", "Delivered/Received"
    INVOICED = "invoiced", "Invoiced/Billed"
    CANCELLED = "cancelled", "Cancelled"


class _OrderBase(TimeStampedModel):
    company = models.ForeignKey(Company, on_delete=models.CASCADE)
    party = models.ForeignKey(Party, on_delete=models.PROTECT)
    date = models.DateField()
    currency = models.ForeignKey(Currency, on_delete=models.PROTECT, related_name="+")
    fx_rate = models.DecimalField(max_digits=18, decimal_places=8, default=Decimal("1"))
    warehouse = models.ForeignKey(Warehouse, null=True, blank=True, on_delete=models.PROTECT, related_name="+")
    reference = models.CharField(max_length=64, blank=True)
    status = models.CharField(max_length=12, choices=DocumentStatus.choices, default=DocumentStatus.DRAFT)

    class Meta:
        abstract = True


class SalesOrder(_OrderBase):
    company = models.ForeignKey(Company, on_delete=models.CASCADE, related_name="sales_orders")

    def __str__(self):
        return f"SO#{self.pk}"


class SalesOrderLine(TimeStampedModel):
    order = models.ForeignKey(SalesOrder, on_delete=models.CASCADE, related_name="lines")
    item = models.ForeignKey(Item, on_delete=models.PROTECT, related_name="+")
    quantity = models.DecimalField(max_digits=18, decimal_places=4)
    unit_price = models.DecimalField(max_digits=18, decimal_places=4)
    tax_code = models.ForeignKey(TaxCode, null=True, blank=True, on_delete=models.PROTECT, related_name="+")

    @property
    def net_amount(self) -> Decimal:
        return (self.quantity * self.unit_price).quantize(Decimal("0.01"))


class PurchaseOrder(_OrderBase):
    company = models.ForeignKey(Company, on_delete=models.CASCADE, related_name="purchase_orders")

    def __str__(self):
        return f"PO#{self.pk}"


class PurchaseOrderLine(TimeStampedModel):
    order = models.ForeignKey(PurchaseOrder, on_delete=models.CASCADE, related_name="lines")
    item = models.ForeignKey(Item, on_delete=models.PROTECT, related_name="+")
    quantity = models.DecimalField(max_digits=18, decimal_places=4)
    unit_price = models.DecimalField(max_digits=18, decimal_places=4)
    tax_code = models.ForeignKey(TaxCode, null=True, blank=True, on_delete=models.PROTECT, related_name="+")

    @property
    def net_amount(self) -> Decimal:
        return (self.quantity * self.unit_price).quantize(Decimal("0.01"))


class FiscalStatus(models.TextChoices):
    NOT_REQUIRED = "not_required", "Not required"
    PENDING = "pending", "Pending fiscalization"
    CLEARED = "cleared", "Cleared / Reported"
    FAILED = "failed", "Failed"


class CustomerInvoice(TimeStampedModel):
    company = models.ForeignKey(Company, on_delete=models.CASCADE, related_name="customer_invoices")
    party = models.ForeignKey(Party, on_delete=models.PROTECT, related_name="customer_invoices")
    sales_order = models.ForeignKey(SalesOrder, null=True, blank=True, on_delete=models.SET_NULL, related_name="invoices")
    date = models.DateField()
    currency = models.ForeignKey(Currency, on_delete=models.PROTECT, related_name="+")
    fx_rate = models.DecimalField(max_digits=18, decimal_places=8, default=Decimal("1"))
    number = models.CharField(max_length=40, blank=True)
    net_total = models.DecimalField(max_digits=18, decimal_places=2, default=ZERO)
    tax_total = models.DecimalField(max_digits=18, decimal_places=2, default=ZERO)
    grand_total = models.DecimalField(max_digits=18, decimal_places=2, default=ZERO)
    amount_paid = models.DecimalField(max_digits=18, decimal_places=2, default=ZERO)
    status = models.CharField(max_length=12, choices=DocumentStatus.choices, default=DocumentStatus.DRAFT)

    # Fiscalization / e-invoicing.
    fiscal_status = models.CharField(max_length=14, choices=FiscalStatus.choices, default=FiscalStatus.PENDING)
    fbr_invoice_number = models.CharField(max_length=64, blank=True)  # Pakistan
    qr_payload = models.TextField(blank=True)                          # PK QR / UAE
    peppol_id = models.CharField(max_length=128, blank=True)           # UAE transmission id

    journal_entry = models.ForeignKey("accounting.JournalEntry", null=True, blank=True, on_delete=models.SET_NULL, related_name="+")

    class Meta:
        ordering = ["-date", "-id"]

    def __str__(self):
        return self.number or f"INV-draft-{self.pk}"

    @property
    def amount_due(self) -> Decimal:
        return self.grand_total - self.amount_paid


class CustomerInvoiceLine(TimeStampedModel):
    invoice = models.ForeignKey(CustomerInvoice, on_delete=models.CASCADE, related_name="lines")
    item = models.ForeignKey(Item, on_delete=models.PROTECT, related_name="+")
    description = models.CharField(max_length=255, blank=True)
    quantity = models.DecimalField(max_digits=18, decimal_places=4)
    unit_price = models.DecimalField(max_digits=18, decimal_places=4)
    tax_code = models.ForeignKey(TaxCode, null=True, blank=True, on_delete=models.PROTECT, related_name="+")
    net_amount = models.DecimalField(max_digits=18, decimal_places=2, default=ZERO)
    tax_amount = models.DecimalField(max_digits=18, decimal_places=2, default=ZERO)


class SupplierBill(TimeStampedModel):
    company = models.ForeignKey(Company, on_delete=models.CASCADE, related_name="supplier_bills")
    party = models.ForeignKey(Party, on_delete=models.PROTECT, related_name="supplier_bills")
    purchase_order = models.ForeignKey(PurchaseOrder, null=True, blank=True, on_delete=models.SET_NULL, related_name="bills")
    date = models.DateField()
    currency = models.ForeignKey(Currency, on_delete=models.PROTECT, related_name="+")
    fx_rate = models.DecimalField(max_digits=18, decimal_places=8, default=Decimal("1"))
    number = models.CharField(max_length=40, blank=True)
    net_total = models.DecimalField(max_digits=18, decimal_places=2, default=ZERO)
    tax_total = models.DecimalField(max_digits=18, decimal_places=2, default=ZERO)
    grand_total = models.DecimalField(max_digits=18, decimal_places=2, default=ZERO)
    amount_paid = models.DecimalField(max_digits=18, decimal_places=2, default=ZERO)
    status = models.CharField(max_length=12, choices=DocumentStatus.choices, default=DocumentStatus.DRAFT)
    journal_entry = models.ForeignKey("accounting.JournalEntry", null=True, blank=True, on_delete=models.SET_NULL, related_name="+")

    class Meta:
        ordering = ["-date", "-id"]

    def __str__(self):
        return self.number or f"BILL-draft-{self.pk}"

    @property
    def amount_due(self) -> Decimal:
        return self.grand_total - self.amount_paid


class SupplierBillLine(TimeStampedModel):
    bill = models.ForeignKey(SupplierBill, on_delete=models.CASCADE, related_name="lines")
    item = models.ForeignKey(Item, on_delete=models.PROTECT, related_name="+")
    description = models.CharField(max_length=255, blank=True)
    quantity = models.DecimalField(max_digits=18, decimal_places=4)
    unit_price = models.DecimalField(max_digits=18, decimal_places=4)
    tax_code = models.ForeignKey(TaxCode, null=True, blank=True, on_delete=models.PROTECT, related_name="+")
    net_amount = models.DecimalField(max_digits=18, decimal_places=2, default=ZERO)
    tax_amount = models.DecimalField(max_digits=18, decimal_places=2, default=ZERO)


class Payment(TimeStampedModel):
    class Direction(models.TextChoices):
        INBOUND = "in", "Inbound (from customer)"
        OUTBOUND = "out", "Outbound (to supplier)"

    company = models.ForeignKey(Company, on_delete=models.CASCADE, related_name="payments")
    party = models.ForeignKey(Party, on_delete=models.PROTECT, related_name="payments")
    direction = models.CharField(max_length=3, choices=Direction.choices)
    date = models.DateField()
    currency = models.ForeignKey(Currency, on_delete=models.PROTECT, related_name="+")
    fx_rate = models.DecimalField(max_digits=18, decimal_places=8, default=Decimal("1"))
    amount = models.DecimalField(max_digits=18, decimal_places=2)
    # 1110 Cash / 1120 Bank.
    cash_account_code = models.CharField(max_length=20, default="1120")
    customer_invoice = models.ForeignKey(CustomerInvoice, null=True, blank=True, on_delete=models.SET_NULL, related_name="payments")
    supplier_bill = models.ForeignKey(SupplierBill, null=True, blank=True, on_delete=models.SET_NULL, related_name="payments")
    journal_entry = models.ForeignKey("accounting.JournalEntry", null=True, blank=True, on_delete=models.SET_NULL, related_name="+")

    def __str__(self):
        return f"PAY {self.direction} {self.amount} {self.currency_id}"
