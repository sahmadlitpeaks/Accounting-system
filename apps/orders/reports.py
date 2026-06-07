"""Receivables / payables aging.

Buckets open document balances by how overdue they are relative to ``as_of``.
Due date = document date + the party's payment terms (days).
"""
from datetime import date, timedelta
from decimal import Decimal

from .models import CustomerInvoice, DocumentStatus, SupplierBill

ZERO = Decimal("0")
BUCKETS = ["current", "1-30", "31-60", "61-90", "90+"]


def _bucket(due_date, as_of) -> str:
    overdue = (as_of - due_date).days
    if overdue <= 0:
        return "current"
    if overdue <= 30:
        return "1-30"
    if overdue <= 60:
        return "31-60"
    if overdue <= 90:
        return "61-90"
    return "90+"


def _age(documents, as_of):
    totals = {b: ZERO for b in BUCKETS}
    detail = []
    for doc in documents:
        due = doc.amount_due
        if due <= ZERO:
            continue
        due_date = doc.date + timedelta(days=doc.party.payment_terms_days)
        bucket = _bucket(due_date, as_of)
        totals[bucket] += due
        detail.append({
            "id": doc.pk,
            "number": doc.number,
            "party": doc.party.name,
            "date": doc.date,
            "due_date": due_date,
            "amount_due": due,
            "bucket": bucket,
        })
    return {"as_of": as_of, "buckets": totals, "total": sum(totals.values(), ZERO), "items": detail}


def ar_aging(company, as_of=None):
    as_of = as_of or date.today()
    invoices = (
        CustomerInvoice.objects.filter(company=company)
        .exclude(status=DocumentStatus.CANCELLED)
        .select_related("party")
    )
    return _age(invoices, as_of)


def ap_aging(company, as_of=None):
    as_of = as_of or date.today()
    bills = (
        SupplierBill.objects.filter(company=company)
        .exclude(status=DocumentStatus.CANCELLED)
        .select_related("party")
    )
    return _age(bills, as_of)
