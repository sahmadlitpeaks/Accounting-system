from django.contrib import admin

from .models import EInvoiceSubmission


@admin.register(EInvoiceSubmission)
class EInvoiceSubmissionAdmin(admin.ModelAdmin):
    list_display = ("id", "document_type", "document_id", "country", "adapter", "status", "attempts", "external_id")
    list_filter = ("status", "country")
    readonly_fields = ("request_payload", "response_payload")
