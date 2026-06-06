"""E-invoicing / fiscalization submission tracking.

One row per attempt to fiscalize a customer invoice. The state machine
(pending -> cleared / failed) is country-agnostic; the adapter fills the
country-specific external identifiers.
"""
from django.db import models

from apps.core.models import Company, TimeStampedModel


class EInvoiceSubmission(TimeStampedModel):
    class Status(models.TextChoices):
        PENDING = "pending", "Pending"
        CLEARED = "cleared", "Cleared / Reported"
        FAILED = "failed", "Failed"

    company = models.ForeignKey(Company, on_delete=models.CASCADE, related_name="einvoice_submissions")
    invoice = models.ForeignKey("orders.CustomerInvoice", on_delete=models.CASCADE, related_name="submissions")
    country = models.CharField(max_length=2)
    adapter = models.CharField(max_length=40)
    status = models.CharField(max_length=8, choices=Status.choices, default=Status.PENDING)
    attempts = models.PositiveSmallIntegerField(default=0)
    external_id = models.CharField(max_length=128, blank=True)
    request_payload = models.TextField(blank=True)
    response_payload = models.TextField(blank=True)
    error = models.TextField(blank=True)

    class Meta:
        ordering = ["-created_at"]

    def __str__(self):
        return f"{self.country} sub for INV#{self.invoice_id} [{self.status}]"
