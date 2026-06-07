from django.contrib import admin

from .models import (
    CustomerCreditNote,
    CustomerCreditNoteLine,
    CustomerInvoice,
    CustomerInvoiceLine,
    Payment,
    PurchaseOrder,
    PurchaseOrderLine,
    SalesOrder,
    SalesOrderLine,
    SupplierBill,
    SupplierBillLine,
)


class SalesOrderLineInline(admin.TabularInline):
    model = SalesOrderLine
    extra = 1


@admin.register(SalesOrder)
class SalesOrderAdmin(admin.ModelAdmin):
    list_display = ("id", "company", "party", "date", "status")
    list_filter = ("status", "company")
    inlines = [SalesOrderLineInline]


class PurchaseOrderLineInline(admin.TabularInline):
    model = PurchaseOrderLine
    extra = 1


@admin.register(PurchaseOrder)
class PurchaseOrderAdmin(admin.ModelAdmin):
    list_display = ("id", "company", "party", "date", "status")
    list_filter = ("status", "company")
    inlines = [PurchaseOrderLineInline]


class CustomerInvoiceLineInline(admin.TabularInline):
    model = CustomerInvoiceLine
    extra = 0


@admin.register(CustomerInvoice)
class CustomerInvoiceAdmin(admin.ModelAdmin):
    list_display = ("id", "number", "company", "party", "date", "grand_total", "status", "fiscal_status", "fbr_invoice_number")
    list_filter = ("status", "fiscal_status", "company")
    inlines = [CustomerInvoiceLineInline]


class SupplierBillLineInline(admin.TabularInline):
    model = SupplierBillLine
    extra = 0


@admin.register(SupplierBill)
class SupplierBillAdmin(admin.ModelAdmin):
    list_display = ("id", "number", "company", "party", "date", "grand_total", "status")
    list_filter = ("status", "company")
    inlines = [SupplierBillLineInline]


class CustomerCreditNoteLineInline(admin.TabularInline):
    model = CustomerCreditNoteLine
    extra = 0


@admin.register(CustomerCreditNote)
class CustomerCreditNoteAdmin(admin.ModelAdmin):
    list_display = ("id", "number", "company", "party", "invoice", "date", "grand_total", "fiscal_status")
    list_filter = ("status", "fiscal_status", "company")
    inlines = [CustomerCreditNoteLineInline]


@admin.register(Payment)
class PaymentAdmin(admin.ModelAdmin):
    list_display = ("id", "company", "party", "direction", "date", "amount")
    list_filter = ("direction", "company")
