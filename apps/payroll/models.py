"""Payroll: employees, monthly runs and payslips.

A posted run books gross salaries to 5210, income-tax withholding (Pakistan)
to 2130, and the net obligation to 2150 Salaries Payable; paying salaries
clears 2150 against the bank. Tax rates live on the employee record — data,
not code — because UAE has no salary income tax while Pakistan does.
"""
from decimal import Decimal

from django.db import models

from apps.core.models import Company, TimeStampedModel

ZERO = Decimal("0")


class Employee(TimeStampedModel):
    company = models.ForeignKey(Company, on_delete=models.CASCADE, related_name="employees")
    employee_no = models.CharField(max_length=20, blank=True)
    name = models.CharField(max_length=128)
    basic_salary = models.DecimalField(max_digits=18, decimal_places=2)
    allowances = models.DecimalField(max_digits=18, decimal_places=2, default=ZERO)
    # Flat income-tax withholding rate (%) applied to gross. 0 for UAE.
    tax_rate = models.DecimalField(max_digits=6, decimal_places=3, default=ZERO)
    is_active = models.BooleanField(default=True)

    class Meta:
        ordering = ["name"]

    def __str__(self):
        return self.name

    @property
    def gross_salary(self) -> Decimal:
        return self.basic_salary + self.allowances


class PayrollRun(TimeStampedModel):
    class Status(models.TextChoices):
        POSTED = "posted", "Posted"
        PAID = "paid", "Paid"

    company = models.ForeignKey(Company, on_delete=models.CASCADE, related_name="payroll_runs")
    period = models.CharField(max_length=7)  # YYYY-MM
    date = models.DateField()
    status = models.CharField(max_length=8, choices=Status.choices, default=Status.POSTED)
    gross_total = models.DecimalField(max_digits=18, decimal_places=2, default=ZERO)
    tax_total = models.DecimalField(max_digits=18, decimal_places=2, default=ZERO)
    net_total = models.DecimalField(max_digits=18, decimal_places=2, default=ZERO)
    journal_entry = models.ForeignKey(
        "accounting.JournalEntry", null=True, blank=True, on_delete=models.SET_NULL, related_name="+"
    )
    payment_entry = models.ForeignKey(
        "accounting.JournalEntry", null=True, blank=True, on_delete=models.SET_NULL, related_name="+"
    )

    class Meta:
        unique_together = ("company", "period")
        ordering = ["-period"]

    def __str__(self):
        return f"Payroll {self.company_id} {self.period}"


class Payslip(TimeStampedModel):
    run = models.ForeignKey(PayrollRun, on_delete=models.CASCADE, related_name="payslips")
    employee = models.ForeignKey(Employee, on_delete=models.PROTECT, related_name="payslips")
    gross = models.DecimalField(max_digits=18, decimal_places=2)
    tax_deduction = models.DecimalField(max_digits=18, decimal_places=2, default=ZERO)
    net_pay = models.DecimalField(max_digits=18, decimal_places=2)

    class Meta:
        unique_together = ("run", "employee")

    def __str__(self):
        return f"{self.employee.name} {self.run.period}: net {self.net_pay}"
