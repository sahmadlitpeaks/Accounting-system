from django.contrib import admin

from .models import (
    Item,
    Party,
    PriceList,
    PriceListItem,
    TaxCode,
    UnitOfMeasure,
    Warehouse,
)


@admin.register(Party)
class PartyAdmin(admin.ModelAdmin):
    list_display = ("name", "company", "is_customer", "is_supplier", "tax_registration_number")
    list_filter = ("is_customer", "is_supplier", "company")
    search_fields = ("name",)


@admin.register(Item)
class ItemAdmin(admin.ModelAdmin):
    list_display = ("sku", "name", "kind", "valuation_method", "sales_price", "company")
    list_filter = ("kind", "valuation_method", "company")
    search_fields = ("sku", "name")


@admin.register(TaxCode)
class TaxCodeAdmin(admin.ModelAdmin):
    list_display = ("name", "kind", "rate", "company", "is_active")
    list_filter = ("kind", "company")


admin.site.register(UnitOfMeasure)
admin.site.register(Warehouse)


class PriceListItemInline(admin.TabularInline):
    model = PriceListItem
    extra = 0


@admin.register(PriceList)
class PriceListAdmin(admin.ModelAdmin):
    list_display = ("name", "company", "currency")
    inlines = [PriceListItemInline]
