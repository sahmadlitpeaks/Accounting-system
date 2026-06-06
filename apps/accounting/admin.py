from django.contrib import admin

from .models import Account, AccountingPeriod, JournalEntry, JournalLine


@admin.register(Account)
class AccountAdmin(admin.ModelAdmin):
    list_display = ("code", "name", "type", "is_group", "company", "is_active")
    list_filter = ("type", "is_group", "company")
    search_fields = ("code", "name")


@admin.register(AccountingPeriod)
class AccountingPeriodAdmin(admin.ModelAdmin):
    list_display = ("name", "company", "start_date", "end_date", "status")
    list_filter = ("status", "company")


class JournalLineInline(admin.TabularInline):
    model = JournalLine
    extra = 0
    readonly_fields = ("base_debit", "base_credit")


@admin.register(JournalEntry)
class JournalEntryAdmin(admin.ModelAdmin):
    list_display = ("id", "date", "company", "memo", "status", "total_debit", "total_credit")
    list_filter = ("status", "company")
    inlines = [JournalLineInline]
    readonly_fields = ("status",)
