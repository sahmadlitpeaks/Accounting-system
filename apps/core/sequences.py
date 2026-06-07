"""Gapless document numbering.

``next_number`` allocates the next sequential number for a (company, doc_type,
year) under a row-level lock, so concurrent requests never collide or skip.
"""
from django.db import transaction

from .models import DocumentSequence

DEFAULT_PREFIXES = {
    "customer_invoice": "INV",
    "supplier_bill": "BILL",
    "customer_credit_note": "CRN",
    "payment": "PAY",
}


@transaction.atomic
def next_number(company, doc_type: str, on_date, prefix: str | None = None) -> str:
    year = on_date.year
    prefix = prefix or DEFAULT_PREFIXES.get(doc_type, doc_type[:4].upper())
    seq, _ = DocumentSequence.objects.select_for_update().get_or_create(
        company=company, doc_type=doc_type, year=year, defaults={"prefix": prefix},
    )
    seq.last_number += 1
    seq.save(update_fields=["last_number", "updated_at"])
    return f"{seq.prefix}-{year}-{seq.last_number:06d}"
