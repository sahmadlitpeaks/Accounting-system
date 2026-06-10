"""Tax return data: the numbers a VAT return (UAE) / sales tax return (Pakistan)
is prepared from.

Output tax comes from customer invoices less credit notes; input tax from
supplier bills; withholding deducted at source is reported separately (it is a
liability owed to the tax authority, not part of net VAT/GST).
"""
from decimal import Decimal

from django.db.models import Sum

from apps.orders.models import (
    CustomerCreditNoteLine,
    CustomerInvoiceLine,
    SupplierBill,
    SupplierBillLine,
)

ZERO = Decimal("0")


def _sum_lines(model, company, start, end, date_field):
    qs = model.objects.filter(**{
        f"{date_field}__company": company,
        f"{date_field}__date__gte": start,
        f"{date_field}__date__lte": end,
    })
    rows = (
        qs.values("tax_code__id", "tax_code__name", "tax_code__rate")
        .annotate(net=Sum("net_amount"), tax=Sum("tax_amount"))
        .order_by("tax_code__name")
    )
    return [
        {
            "tax_code": r["tax_code__name"] or "(untaxed)",
            "rate": r["tax_code__rate"] or ZERO,
            "net": r["net"] or ZERO,
            "tax": r["tax"] or ZERO,
        }
        for r in rows
    ]


def tax_return(company, start, end) -> dict:
    sales = _sum_lines(CustomerInvoiceLine, company, start, end, "invoice")
    credits = _sum_lines(CustomerCreditNoteLine, company, start, end, "credit_note")
    purchases = _sum_lines(SupplierBillLine, company, start, end, "bill")

    output_tax = sum((r["tax"] for r in sales), ZERO) - sum((r["tax"] for r in credits), ZERO)
    input_tax = sum((r["tax"] for r in purchases), ZERO)
    wht = SupplierBill.objects.filter(
        company=company, date__gte=start, date__lte=end
    ).aggregate(s=Sum("withholding_total"))["s"] or ZERO

    return {
        "company": company.id,
        "period": {"start": start, "end": end},
        "sales": sales,
        "credit_notes": credits,
        "purchases": purchases,
        "output_tax": output_tax,
        "input_tax": input_tax,
        "net_tax_payable": output_tax - input_tax,
        "withholding_deducted": wht,
    }
