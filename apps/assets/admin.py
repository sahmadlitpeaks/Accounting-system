from django.contrib import admin

from .models import AssetCategory, DepreciationEntry, FixedAsset


@admin.register(AssetCategory)
class AssetCategoryAdmin(admin.ModelAdmin):
    list_display = ("name", "company", "useful_life_months")
    list_filter = ("company",)


class DepreciationEntryInline(admin.TabularInline):
    model = DepreciationEntry
    extra = 0
    readonly_fields = ("period", "amount", "journal_entry")


@admin.register(FixedAsset)
class FixedAssetAdmin(admin.ModelAdmin):
    list_display = ("name", "company", "category", "acquisition_date", "cost",
                    "accumulated_depreciation", "book_value", "status")
    list_filter = ("status", "company", "category")
    inlines = [DepreciationEntryInline]
