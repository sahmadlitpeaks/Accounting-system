from django.contrib import admin

from .models import StockMove, StockValuationLayer


@admin.register(StockMove)
class StockMoveAdmin(admin.ModelAdmin):
    list_display = ("item", "warehouse", "date", "quantity", "unit_cost", "value", "source_type")
    list_filter = ("warehouse", "company")
    search_fields = ("item__sku",)


@admin.register(StockValuationLayer)
class StockValuationLayerAdmin(admin.ModelAdmin):
    list_display = ("item", "warehouse", "remaining_qty", "unit_cost", "remaining_value")
    list_filter = ("warehouse", "company")
