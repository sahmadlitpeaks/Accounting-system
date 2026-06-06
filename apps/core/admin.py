from django.contrib import admin

from .models import Company, Currency, ExchangeRate


@admin.register(Currency)
class CurrencyAdmin(admin.ModelAdmin):
    list_display = ("code", "name", "symbol", "decimal_places")


@admin.register(Company)
class CompanyAdmin(admin.ModelAdmin):
    list_display = ("name", "country_code", "base_currency", "tax_registration_number", "is_active")
    list_filter = ("country_code", "is_active")


@admin.register(ExchangeRate)
class ExchangeRateAdmin(admin.ModelAdmin):
    list_display = ("from_currency", "to_currency", "date", "rate", "source")
    list_filter = ("from_currency", "to_currency")
