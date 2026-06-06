"""Async fiscalization tasks. Retries with exponential backoff because the ASP /
FBR integrator may be slow or temporarily unavailable."""
from celery import shared_task


@shared_task(bind=True, max_retries=5, default_retry_delay=10)
def submit_invoice_task(self, submission_id: int):
    from .services import process_submission

    try:
        process_submission(submission_id)
    except Exception as exc:  # noqa: BLE001
        raise self.retry(exc=exc)
