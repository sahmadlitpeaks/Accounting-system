"""Bank reconciliation: imported statements matched against recorded payments.

A statement line with a positive amount is money received (matches inbound
payments); negative is money out (matches outbound payments).
"""
from django.db import models

from apps.core.models import Company, Currency, TimeStampedModel


class BankAccount(TimeStampedModel):
    company = models.ForeignKey(Company, on_delete=models.CASCADE, related_name="bank_accounts")
    name = models.CharField(max_length=64)
    iban = models.CharField(max_length=34, blank=True)
    currency = models.ForeignKey(Currency, on_delete=models.PROTECT, related_name="+")
    # GL account this bank account maps to (e.g. 1120 Bank Accounts).
    gl_account_code = models.CharField(max_length=20, default="1120")

    class Meta:
        unique_together = ("company", "name")

    def __str__(self):
        return f"{self.name} ({self.currency_id})"


class BankStatement(TimeStampedModel):
    bank_account = models.ForeignKey(BankAccount, on_delete=models.CASCADE, related_name="statements")
    reference = models.CharField(max_length=64, blank=True)
    statement_date = models.DateField()

    class Meta:
        ordering = ["-statement_date"]

    def __str__(self):
        return f"{self.bank_account.name} stmt {self.statement_date}"

    @property
    def unmatched_count(self) -> int:
        return self.lines.filter(status=BankStatementLine.Status.UNMATCHED).count()


class BankStatementLine(TimeStampedModel):
    class Status(models.TextChoices):
        UNMATCHED = "unmatched", "Unmatched"
        MATCHED = "matched", "Matched"
        MANUAL = "manual", "Matched manually"

    statement = models.ForeignKey(BankStatement, on_delete=models.CASCADE, related_name="lines")
    date = models.DateField()
    description = models.CharField(max_length=255, blank=True)
    # Signed: positive = credit to our account (money in), negative = money out.
    amount = models.DecimalField(max_digits=18, decimal_places=2)
    status = models.CharField(max_length=10, choices=Status.choices, default=Status.UNMATCHED)
    matched_payment = models.ForeignKey(
        "orders.Payment", null=True, blank=True, on_delete=models.SET_NULL, related_name="bank_lines"
    )

    class Meta:
        ordering = ["date", "id"]

    def __str__(self):
        return f"{self.date} {self.amount} [{self.status}]"
