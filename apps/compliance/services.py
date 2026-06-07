"""Fiscalization orchestration.

``submit_document`` creates a submission record and dispatches the async task.
The task calls the country adapter and updates the document's fiscal status. A
document is only legally "cleared" once the adapter reports success. Works for
any fiscal document (customer invoice, credit note) — they share the same shape.
"""
from django.db import transaction

from .adapters import get_adapter
from .models import EInvoiceSubmission

# B2C is currently out of scope for UAE e-invoicing; both countries here are B2B.


def submit_document(document, document_type: str):
    """Queue a fiscal document for e-invoicing. Idempotent: an already-cleared
    document is not re-submitted."""
    from apps.orders.models import FiscalStatus

    if document.fiscal_status == FiscalStatus.CLEARED:
        return None

    submission = EInvoiceSubmission.objects.create(
        company=document.company,
        document_type=document_type,
        document_id=str(document.pk),
        country=document.company.country_code,
        adapter=get_adapter(document.company.country_code).name,
        status=EInvoiceSubmission.Status.PENDING,
    )
    from .tasks import submit_invoice_task
    transaction.on_commit(lambda: submit_invoice_task.delay(submission.id))
    return submission


def submit_invoice(invoice):
    """Backwards-compatible helper for customer invoices."""
    return submit_document(invoice, "customer_invoice")


def process_submission(submission_id: int):
    """Run one submission attempt synchronously (called by the Celery task)."""
    from apps.orders.models import FiscalStatus

    submission = EInvoiceSubmission.objects.select_related("company").get(pk=submission_id)
    document = submission.load_document()
    submission.attempts += 1
    adapter = get_adapter(submission.country)
    try:
        result = adapter.submit(document)
    except Exception as exc:  # noqa: BLE001 - record and let Celery retry
        submission.status = EInvoiceSubmission.Status.FAILED
        submission.error = str(exc)
        submission.save()
        document.fiscal_status = FiscalStatus.FAILED
        document.save(update_fields=["fiscal_status"])
        raise

    if result.success:
        submission.status = EInvoiceSubmission.Status.CLEARED
        submission.external_id = result.external_id
        submission.request_payload = result.request_payload
        submission.response_payload = result.response_payload
        submission.save()
        document.fiscal_status = FiscalStatus.CLEARED
        if result.fbr_invoice_number:
            document.fbr_invoice_number = result.fbr_invoice_number
        if result.peppol_id:
            document.peppol_id = result.peppol_id
        if result.qr_payload:
            document.qr_payload = result.qr_payload
        document.save(update_fields=["fiscal_status", "fbr_invoice_number", "peppol_id", "qr_payload"])
    else:
        submission.status = EInvoiceSubmission.Status.FAILED
        submission.error = result.error
        submission.response_payload = result.response_payload
        submission.save()
        document.fiscal_status = FiscalStatus.FAILED
        document.save(update_fields=["fiscal_status"])
    return submission
