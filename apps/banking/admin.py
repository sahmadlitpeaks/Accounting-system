from django.contrib import admin

from .models import BankAccount, BankStatement, BankStatementLine


@admin.register(BankAccount)
class BankAccountAdmin(admin.ModelAdmin):
    list_display = ("name", "company", "currency", "iban", "gl_account_code")
    list_filter = ("company",)


class BankStatementLineInline(admin.TabularInline):
    model = BankStatementLine
    extra = 0


@admin.register(BankStatement)
class BankStatementAdmin(admin.ModelAdmin):
    list_display = ("bank_account", "statement_date", "reference", "unmatched_count")
    inlines = [BankStatementLineInline]
