"""Rule-driven tax computation.

Rates live on :class:`masterdata.TaxCode` (data, never hard-coded), so the same
engine serves UAE VAT 5%, Pakistan GST 18%, withholding, zero-rated and exempt.
"""
from decimal import Decimal

from apps.masterdata.models import TaxCode

ZERO = Decimal("0")


def _q2(value: Decimal) -> Decimal:
    return Decimal(value).quantize(Decimal("0.01"))


def line_tax(net_amount: Decimal, tax_code: TaxCode | None) -> Decimal:
    """Tax amount for a net (tax-exclusive) line amount. Exempt/zero -> 0."""
    if tax_code is None or tax_code.kind in (TaxCode.Kind.EXEMPT, TaxCode.Kind.ZERO):
        return ZERO
    return _q2(Decimal(net_amount) * tax_code.rate / Decimal("100"))


def summarize(lines) -> dict:
    """Aggregate net / tax / gross across an iterable of (net_amount, tax_code).

    Returns totals plus a per-tax-code breakdown (useful for tax returns and for
    grouping ``output_account`` postings).
    """
    net_total = ZERO
    tax_total = ZERO
    by_code: dict = {}
    for net_amount, tax_code in lines:
        net = Decimal(net_amount)
        tax = line_tax(net, tax_code)
        net_total += net
        tax_total += tax
        key = tax_code.id if tax_code else None
        bucket = by_code.setdefault(
            key, {"tax_code": tax_code, "net": ZERO, "tax": ZERO}
        )
        bucket["net"] += net
        bucket["tax"] += tax
    return {
        "net": _q2(net_total),
        "tax": _q2(tax_total),
        "gross": _q2(net_total + tax_total),
        "by_code": by_code,
    }
