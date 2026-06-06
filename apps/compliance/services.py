"""Fiscalization orchestration.

``submit_invoice`` creates a submission record and dispatches the async task.
The task calls the country adapter and updates the invoice's fiscal status. The
invoice is only legally "cleared" once the adapter reports success.
"""
from django.db import transaction

from .adapters import get_adapter
from .models import EInvoiceSubmission

# B2C is currently out of scope for UAE e-invoicing; both countries here are B2B.


def submit_invoice(invoice):
    """Queue a customer invoice for statutory e-invoicing. Idempotent: an
    already-cleared invoice is not re-submitted."""
    from apps.orders.models import FiscalStatus

    if invoice.fiscal_status == FiscalStatus.CLEARED:
        return None

    submission = EInvoiceSubmission.objects.create(
        company=invoice.company,
        invoice=invoice,
        country=invoice.company.country_code,
        adapter=get_adapter(invoice.company.country_code).name,
        status=EInvoiceSubmission.Status.PENDING,
    )
    # Dispatch after the surrounding transaction commits so the worker sees rows.
    from .tasks import submit_invoice_task
    transaction.on_commit(lambda: submit_invoice_task.delay(submission.id))
    return submission


def process_submission(submission_id: int):
    """Run one submission attempt synchronously (called by the Celery task)."""
    from apps.orders.models import FiscalStatus

    submission = EInvoiceSubmission.objects.select_related("invoice", "company").get(pk=submission_id)
    invoice = submission.invoice
    submission.attempts += 1
    adapter = get_adapter(submission.country)
    try:
        result = adapter.submit(invoice)
    except Exception as exc:  # noqa: BLE001 - record and let Celery retry
        submission.status = EInvoiceSubmission.Status.FAILED
        submission.error = str(exc)
        submission.save()
        invoice.fiscal_status = FiscalStatus.FAILED
        invoice.save(update_fields=["fiscal_status"])
        raise

    if result.success:
        submission.status = EInvoiceSubmission.Status.CLEARED
        submission.external_id = result.external_id
        submission.request_payload = result.request_payload
        submission.response_payload = result.response_payload
        submission.save()
        invoice.fiscal_status = FiscalStatus.CLEARED
        if result.fbr_invoice_number:
            invoice.fbr_invoice_number = result.fbr_invoice_number
        if result.peppol_id:
            invoice.peppol_id = result.peppol_id
        if result.qr_payload:
            invoice.qr_payload = result.qr_payload
        invoice.save(update_fields=["fiscal_status", "fbr_invoice_number", "peppol_id", "qr_payload"])
    else:
        submission.status = EInvoiceSubmission.Status.FAILED
        submission.error = result.error
        submission.response_payload = result.response_payload
        submission.save()
        invoice.fiscal_status = FiscalStatus.FAILED
        invoice.save(update_fields=["fiscal_status"])
    return submission
