"""Double-entry accounting core.

The five fundamental account types satisfy the accounting equation:
    Assets = Liabilities + Equity + (Income - Expenses)

Posted journal entries are immutable; corrections are made with reversing
entries / credit notes, never edits.
"""
from decimal import Decimal

from django.core.exceptions import ValidationError
from django.db import models

from apps.core.models import Company, Currency, TimeStampedModel

ZERO = Decimal("0")


class AccountType(models.TextChoices):
    ASSET = "asset", "Asset"
    LIABILITY = "liability", "Liability"
    EQUITY = "equity", "Equity / Capital"
    INCOME = "income", "Income"
    EXPENSE = "expense", "Expense"


# Accounts whose balance naturally increases on the debit side.
DEBIT_NORMAL_TYPES = {AccountType.ASSET, AccountType.EXPENSE}


def normal_balance_for(account_type: str) -> str:
    return "debit" if account_type in DEBIT_NORMAL_TYPES else "credit"


class Account(TimeStampedModel):
    """A node in the Chart of Accounts. Group accounts organise the tree and
    cannot be posted to; only leaf (non-group) accounts receive journal lines."""

    company = models.ForeignKey(Company, on_delete=models.CASCADE, related_name="accounts")
    code = models.CharField(max_length=20)
    name = models.CharField(max_length=128)
    type = models.CharField(max_length=12, choices=AccountType.choices)
    subtype = models.CharField(max_length=40, blank=True)
    parent = models.ForeignKey(
        "self", null=True, blank=True, on_delete=models.PROTECT, related_name="children"
    )
    is_group = models.BooleanField(default=False)
    is_active = models.BooleanField(default=True)

    class Meta:
        unique_together = ("company", "code")
        ordering = ["company", "code"]

    def __str__(self):
        return f"{self.code} {self.name}"

    @property
    def normal_balance(self) -> str:
        return normal_balance_for(self.type)


class AccountingPeriod(TimeStampedModel):
    """A fiscal period. Posting into a closed period is rejected."""

    class Status(models.TextChoices):
        OPEN = "open", "Open"
        CLOSED = "closed", "Closed"

    company = models.ForeignKey(Company, on_delete=models.CASCADE, related_name="periods")
    name = models.CharField(max_length=32)  # e.g. "2026-06"
    start_date = models.DateField()
    end_date = models.DateField()
    status = models.CharField(max_length=8, choices=Status.choices, default=Status.OPEN)

    class Meta:
        unique_together = ("company", "name")
        ordering = ["company", "start_date"]

    def __str__(self):
        return f"{self.company_id}:{self.name}"

    def contains(self, on_date) -> bool:
        return self.start_date <= on_date <= self.end_date


class JournalEntry(TimeStampedModel):
    """A balanced set of journal lines. Immutable once posted."""

    class Status(models.TextChoices):
        DRAFT = "draft", "Draft"
        POSTED = "posted", "Posted"
        VOID = "void", "Void"

    company = models.ForeignKey(Company, on_delete=models.CASCADE, related_name="journal_entries")
    date = models.DateField()
    period = models.ForeignKey(
        AccountingPeriod, null=True, blank=True, on_delete=models.PROTECT, related_name="entries"
    )
    reference = models.CharField(max_length=64, blank=True)
    memo = models.CharField(max_length=255, blank=True)
    # Loose link back to the originating document (invoice, payment, stock move…).
    source_type = models.CharField(max_length=40, blank=True)
    source_id = models.CharField(max_length=40, blank=True)
    status = models.CharField(max_length=8, choices=Status.choices, default=Status.DRAFT)
    reversal_of = models.ForeignKey(
        "self", null=True, blank=True, on_delete=models.PROTECT, related_name="reversals"
    )

    class Meta:
        ordering = ["-date", "-id"]
        verbose_name_plural = "journal entries"

    def __str__(self):
        return f"JE#{self.pk} {self.date} [{self.status}]"

    @property
    def total_debit(self) -> Decimal:
        return sum((line.base_debit for line in self.lines.all()), ZERO)

    @property
    def total_credit(self) -> Decimal:
        return sum((line.base_credit for line in self.lines.all()), ZERO)

    @property
    def is_balanced(self) -> bool:
        return self.total_debit == self.total_credit


class JournalLine(TimeStampedModel):
    """One side of a posting. ``debit``/``credit`` are in the line currency;
    ``base_debit``/``base_credit`` are in the company's base currency and are
    what the balancing invariant is checked against."""

    entry = models.ForeignKey(JournalEntry, on_delete=models.CASCADE, related_name="lines")
    account = models.ForeignKey(Account, on_delete=models.PROTECT, related_name="lines")
    description = models.CharField(max_length=255, blank=True)

    currency = models.ForeignKey(Currency, on_delete=models.PROTECT, related_name="+")
    fx_rate = models.DecimalField(max_digits=18, decimal_places=8, default=Decimal("1"))
    debit = models.DecimalField(max_digits=18, decimal_places=2, default=ZERO)
    credit = models.DecimalField(max_digits=18, decimal_places=2, default=ZERO)
    base_debit = models.DecimalField(max_digits=18, decimal_places=2, default=ZERO)
    base_credit = models.DecimalField(max_digits=18, decimal_places=2, default=ZERO)

    # Optional sub-ledger link (AR/AP) to a customer or supplier.
    party = models.ForeignKey(
        "masterdata.Party", null=True, blank=True, on_delete=models.PROTECT, related_name="journal_lines"
    )

    class Meta:
        ordering = ["id"]

    def __str__(self):
        return f"{self.account.code} D{self.base_debit} C{self.base_credit}"

    def clean(self):
        if self.debit < ZERO or self.credit < ZERO:
            raise ValidationError("Debit and credit must be non-negative.")
        if self.debit > ZERO and self.credit > ZERO:
            raise ValidationError("A line cannot have both a debit and a credit.")
        if self.debit == ZERO and self.credit == ZERO:
            raise ValidationError("A line must have either a debit or a credit.")
