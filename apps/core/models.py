"""Core, cross-cutting models: timestamps, multi-company, currency, FX."""
from decimal import Decimal

from django.db import models


class TimeStampedModel(models.Model):
    """Abstract base giving every row created/updated audit timestamps."""

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        abstract = True


class Currency(models.Model):
    """ISO-4217 currency. ``decimal_places`` drives money rounding."""

    code = models.CharField(max_length=3, primary_key=True)  # AED, PKR, USD
    name = models.CharField(max_length=64)
    symbol = models.CharField(max_length=8, blank=True)
    decimal_places = models.PositiveSmallIntegerField(default=2)

    class Meta:
        verbose_name_plural = "currencies"
        ordering = ["code"]

    def __str__(self):
        return self.code


class Company(TimeStampedModel):
    """A legal entity. The system is multi-company: every transactional row
    references a company, and ledgers/sequences/tax settings are per-company."""

    COUNTRY_CHOICES = [("AE", "United Arab Emirates"), ("PK", "Pakistan")]

    name = models.CharField(max_length=128)
    country_code = models.CharField(max_length=2, choices=COUNTRY_CHOICES)
    base_currency = models.ForeignKey(Currency, on_delete=models.PROTECT, related_name="companies")
    tax_registration_number = models.CharField(
        max_length=32, blank=True, help_text="TRN (UAE) / STRN or NTN (Pakistan)"
    )
    fiscal_year_start_month = models.PositiveSmallIntegerField(default=1)
    is_active = models.BooleanField(default=True)

    class Meta:
        verbose_name_plural = "companies"
        ordering = ["name"]

    def __str__(self):
        return f"{self.name} ({self.country_code})"


class ExchangeRate(TimeStampedModel):
    """Rate to convert ``from_currency`` -> ``to_currency`` on a given date.

    amount_in_to = amount_in_from * rate
    """

    from_currency = models.ForeignKey(Currency, on_delete=models.PROTECT, related_name="+")
    to_currency = models.ForeignKey(Currency, on_delete=models.PROTECT, related_name="+")
    date = models.DateField()
    rate = models.DecimalField(max_digits=18, decimal_places=8)
    source = models.CharField(max_length=64, blank=True)

    class Meta:
        unique_together = ("from_currency", "to_currency", "date")
        ordering = ["-date"]

    def __str__(self):
        return f"{self.from_currency}->{self.to_currency} @ {self.rate} ({self.date})"

    @classmethod
    def convert(cls, amount: Decimal, from_code: str, to_code: str, on_date) -> Decimal:
        """Convert an amount using the latest rate on/before ``on_date``.

        Returns the amount unchanged when currencies match.
        """
        if from_code == to_code:
            return amount
        rate = (
            cls.objects.filter(
                from_currency_id=from_code, to_currency_id=to_code, date__lte=on_date
            )
            .order_by("-date")
            .values_list("rate", flat=True)
            .first()
        )
        if rate is None:
            raise ValueError(f"No exchange rate {from_code}->{to_code} on/before {on_date}")
        return amount * rate
