"""Unrealised FX revaluation of open foreign-currency receivables/payables.

At period end, every open customer invoice / supplier bill denominated in a
foreign currency is restated at the latest exchange rate. The difference between
the booked base value (outstanding x document rate) and the current base value
(outstanding x market rate) posts to FX gain (4900) / FX loss (5900) against
AR (1130) / AP (2110).

Convention: posts one adjustment entry per run; running again after rates move
posts a further adjustment relative to the document rate, so reverse prior
revaluation entries first if you re-run for the same date (standard practice is
to reverse them at the start of the next period).
"""
from decimal import Decimal

from django.db import transaction

from apps.accounting.services import EntryInput, LineInput, get_account, post_entry
from apps.core.models import ExchangeRate

from .models import ZERO, CustomerInvoice, DocumentStatus, SupplierBill


def _q2(value: Decimal) -> Decimal:
    return Decimal(value).quantize(Decimal("0.01"))


def _rate(from_code: str, to_code: str, on_date) -> Decimal:
    return ExchangeRate.convert(Decimal("1"), from_code, to_code, on_date)


@transaction.atomic
def revalue_open_documents(company, as_of) -> object:
    """Post the unrealised FX revaluation entry. Returns the journal entry, or
    None when there is nothing to revalue."""
    base = company.base_currency_id
    ar_adjust = ZERO   # signed: positive = AR base value increased (gain)
    ap_adjust = ZERO   # signed: positive = AP base value increased (loss)

    invoices = CustomerInvoice.objects.filter(company=company).exclude(
        status=DocumentStatus.CANCELLED).exclude(currency_id=base)
    for inv in invoices:
        outstanding = inv.amount_due
        if outstanding <= ZERO:
            continue
        current = _q2(outstanding * _rate(inv.currency_id, base, as_of))
        booked = _q2(outstanding * inv.fx_rate)
        ar_adjust += current - booked

    bills = SupplierBill.objects.filter(company=company).exclude(
        status=DocumentStatus.CANCELLED).exclude(currency_id=base)
    for bill in bills:
        outstanding = bill.amount_due
        if outstanding <= ZERO:
            continue
        current = _q2(outstanding * _rate(bill.currency_id, base, as_of))
        booked = _q2(outstanding * bill.fx_rate)
        ap_adjust += current - booked

    lines = []
    if ar_adjust > 0:
        lines += [LineInput(account=get_account(company, "1130"), debit=_q2(ar_adjust)),
                  LineInput(account=get_account(company, "4900"), credit=_q2(ar_adjust),
                            description="Unrealised FX gain on receivables")]
    elif ar_adjust < 0:
        lines += [LineInput(account=get_account(company, "5900"), debit=_q2(-ar_adjust),
                            description="Unrealised FX loss on receivables"),
                  LineInput(account=get_account(company, "1130"), credit=_q2(-ar_adjust))]
    if ap_adjust > 0:
        lines += [LineInput(account=get_account(company, "5900"), debit=_q2(ap_adjust),
                            description="Unrealised FX loss on payables"),
                  LineInput(account=get_account(company, "2110"), credit=_q2(ap_adjust))]
    elif ap_adjust < 0:
        lines += [LineInput(account=get_account(company, "2110"), debit=_q2(-ap_adjust)),
                  LineInput(account=get_account(company, "4900"), credit=_q2(-ap_adjust),
                            description="Unrealised FX gain on payables")]

    if not lines:
        return None
    return post_entry(EntryInput(
        company=company, date=as_of,
        memo=f"FX revaluation as of {as_of}",
        source_type="fx_revaluation", source_id=str(as_of),
        lines=lines,
    ))
