from django.contrib import admin

from .models import BillOfMaterial, BOMLine, WorkOrder


class BOMLineInline(admin.TabularInline):
    model = BOMLine
    extra = 1


@admin.register(BillOfMaterial)
class BillOfMaterialAdmin(admin.ModelAdmin):
    list_display = ("product", "company", "name", "is_active")
    list_filter = ("company", "is_active")
    inlines = [BOMLineInline]


@admin.register(WorkOrder)
class WorkOrderAdmin(admin.ModelAdmin):
    list_display = ("id", "bom", "quantity", "warehouse", "date", "status", "produced_cost")
    list_filter = ("status", "company")
