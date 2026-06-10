from django.contrib import admin

from .models import Employee, PayrollRun, Payslip


@admin.register(Employee)
class EmployeeAdmin(admin.ModelAdmin):
    list_display = ("name", "company", "basic_salary", "allowances", "tax_rate", "is_active")
    list_filter = ("company", "is_active")


class PayslipInline(admin.TabularInline):
    model = Payslip
    extra = 0
    readonly_fields = ("employee", "gross", "tax_deduction", "net_pay")


@admin.register(PayrollRun)
class PayrollRunAdmin(admin.ModelAdmin):
    list_display = ("company", "period", "status", "gross_total", "tax_total", "net_total")
    list_filter = ("status", "company")
    inlines = [PayslipInline]
