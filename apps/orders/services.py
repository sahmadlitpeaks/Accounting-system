"""Order orchestration: wires sales/purchase documents to inventory, the GL,
and (for customer invoices) the fiscalization/e-invoicing pipeline.

Account codes used (resolved from the company's seeded Chart of Accounts):
  1110 Cash · 1120 Bank · 1130 AR · 1140 Inventory · 1150 Input tax
  2110 AP · 2120 Output tax · 2140 GRNI
  4100 Sales-Goods · 4200 Sales-Services · 5100 COGS
"""
from decimal import Decimal

from django.db import transaction

from apps.accounting.services import EntryInput, LineInput, get_account, post_entry
from apps.inventory.services import issue_stock, receive_stock
from apps.masterdata.models import Item
from apps.tax.services import line_tax

from .models import (
    ZERO,
    CustomerInvoice,
    CustomerInvoiceLine,
    DocumentStatus,
    FiscalStatus,
    Payment,
    PurchaseOrder,
    SalesOrder,
    SupplierBill,
    SupplierBillLine,
)


class OrderError(Exception):
    pass


def _q2(value: Decimal) -> Decimal:
    return Decimal(value).quantize(Decimal("0.01"))


def _revenue_code(item: Item) -> str:
    return "4100" if item.kind == Item.Kind.STOCK else "4200"


# --------------------------------------------------------------------------- #
# Sales: deliver -> invoice
# --------------------------------------------------------------------------- #
@transaction.atomic
def deliver_sales_order(order: SalesOrder):
    """Issue stock for each stock line and post COGS (Dr 5100 / Cr 1140)."""
    if order.status not in (DocumentStatus.DRAFT, DocumentStatus.CONFIRMED):
        raise OrderError(f"Sales order {order.pk} cannot be delivered from {order.status}.")
    if not order.warehouse:
        raise OrderError("Sales order needs a warehouse to deliver stock.")

    total_cogs = ZERO
    for line in order.lines.select_related("item"):
        if line.item.kind != Item.Kind.STOCK:
            continue
        _move, cogs = issue_stock(
            company=order.company, item=line.item, warehouse=order.warehouse,
            quantity=line.quantity, date=order.date,
            source_type="sales_order", source_id=order.pk,
        )
        total_cogs += cogs

    if total_cogs > 0:
        post_entry(EntryInput(
            company=order.company, date=order.date,
            memo=f"COGS for SO#{order.pk}",
            source_type="sales_order", source_id=order.pk,
            lines=[
                LineInput(account=get_account(order.company, "5100"), debit=total_cogs),
                LineInput(account=get_account(order.company, "1140"), credit=total_cogs),
            ],
        ))
    order.status = DocumentStatus.DELIVERED
    order.save(update_fields=["status"])
    return order


@transaction.atomic
def invoice_sales_order(order: SalesOrder, number: str = "") -> CustomerInvoice:
    """Create a customer invoice from the order, post AR/revenue/output-tax,
    then queue it for statutory e-invoicing."""
    invoice = CustomerInvoice.objects.create(
        company=order.company, party=order.party, sales_order=order,
        date=order.date, currency=order.currency, fx_rate=order.fx_rate,
        number=number, status=DocumentStatus.CONFIRMED,
    )
    for line in order.lines.select_related("item", "tax_code"):
        net = _q2(line.quantity * line.unit_price)
        tax = line_tax(net, line.tax_code)
        CustomerInvoiceLine.objects.create(
            invoice=invoice, item=line.item, description=line.item.name,
            quantity=line.quantity, unit_price=line.unit_price,
            tax_code=line.tax_code, net_amount=net, tax_amount=tax,
        )
    _finalize_customer_invoice(invoice)
    order.status = DocumentStatus.INVOICED
    order.save(update_fields=["status"])
    return invoice


@transaction.atomic
def _finalize_customer_invoice(invoice: CustomerInvoice):
    """Total the invoice, post the GL entry, and trigger fiscalization."""
    net_total = ZERO
    tax_total = ZERO
    revenue_by_code: dict = {}
    tax_by_account: dict = {}

    for line in invoice.lines.select_related("item", "tax_code"):
        net_total += line.net_amount
        tax_total += line.tax_amount
        rev_code = _revenue_code(line.item)
        revenue_by_code[rev_code] = revenue_by_code.get(rev_code, ZERO) + line.net_amount
        if line.tax_amount > 0:
            tax_acc = (line.tax_code.output_account_id and line.tax_code.output_account) or get_account(invoice.company, "2120")
            tax_by_account[tax_acc] = tax_by_account.get(tax_acc, ZERO) + line.tax_amount

    grand = _q2(net_total + tax_total)
    invoice.net_total = _q2(net_total)
    invoice.tax_total = _q2(tax_total)
    invoice.grand_total = grand

    lines = [LineInput(
        account=get_account(invoice.company, "1130"), debit=grand,
        currency=invoice.currency, fx_rate=invoice.fx_rate, party=invoice.party,
        description=f"AR {invoice.party.name}",
    )]
    for code, amount in revenue_by_code.items():
        lines.append(LineInput(
            account=get_account(invoice.company, code), credit=_q2(amount),
            currency=invoice.currency, fx_rate=invoice.fx_rate,
        ))
    for tax_acc, amount in tax_by_account.items():
        lines.append(LineInput(
            account=tax_acc, credit=_q2(amount),
            currency=invoice.currency, fx_rate=invoice.fx_rate,
        ))

    entry = post_entry(EntryInput(
        company=invoice.company, date=invoice.date,
        memo=f"Customer invoice {invoice.number or invoice.pk}",
        source_type="customer_invoice", source_id=invoice.pk, lines=lines,
    ))
    invoice.journal_entry = entry
    invoice.fiscal_status = FiscalStatus.PENDING
    invoice.save()

    # Hand off to the country fiscalization adapter (async, idempotent).
    from apps.compliance.services import submit_invoice
    submit_invoice(invoice)
    return invoice


# --------------------------------------------------------------------------- #
# Purchasing: receive -> bill
# --------------------------------------------------------------------------- #
@transaction.atomic
def receive_purchase_order(order: PurchaseOrder):
    """Receive stock into inventory; post Dr 1140 Inventory / Cr 2140 GRNI."""
    if not order.warehouse:
        raise OrderError("Purchase order needs a warehouse to receive stock.")
    total_cost = ZERO
    for line in order.lines.select_related("item"):
        if line.item.kind != Item.Kind.STOCK:
            continue
        cost = _q2(line.quantity * line.unit_price)
        receive_stock(
            company=order.company, item=line.item, warehouse=order.warehouse,
            quantity=line.quantity, unit_cost=line.unit_price, date=order.date,
            source_type="purchase_order", source_id=order.pk,
        )
        total_cost += cost
    if total_cost > 0:
        post_entry(EntryInput(
            company=order.company, date=order.date,
            memo=f"Goods receipt PO#{order.pk}",
            source_type="purchase_order", source_id=order.pk,
            lines=[
                LineInput(account=get_account(order.company, "1140"), debit=total_cost),
                LineInput(account=get_account(order.company, "2140"), credit=total_cost),
            ],
        ))
    order.status = DocumentStatus.DELIVERED
    order.save(update_fields=["status"])
    return order


@transaction.atomic
def bill_purchase_order(order: PurchaseOrder, number: str = "") -> SupplierBill:
    """Create a supplier bill: clear GRNI for stock, expense services, add input
    tax, credit AP (Dr 2140/5xxx + Dr 1150 / Cr 2110)."""
    bill = SupplierBill.objects.create(
        company=order.company, party=order.party, purchase_order=order,
        date=order.date, currency=order.currency, fx_rate=order.fx_rate,
        number=number, status=DocumentStatus.CONFIRMED,
    )
    net_total = ZERO
    tax_total = ZERO
    debit_by_account: dict = {}
    for line in order.lines.select_related("item", "tax_code"):
        net = _q2(line.quantity * line.unit_price)
        tax = line_tax(net, line.tax_code)
        SupplierBillLine.objects.create(
            bill=bill, item=line.item, description=line.item.name,
            quantity=line.quantity, unit_price=line.unit_price,
            tax_code=line.tax_code, net_amount=net, tax_amount=tax,
        )
        net_total += net
        tax_total += tax
        # Stock lines clear GRNI (already in inventory); others go to expense.
        code = "2140" if line.item.kind == Item.Kind.STOCK else "5200"
        acc = get_account(order.company, code)
        debit_by_account[acc] = debit_by_account.get(acc, ZERO) + net
        if tax > 0:
            tax_acc = (line.tax_code.input_account_id and line.tax_code.input_account) or get_account(order.company, "1150")
            debit_by_account[tax_acc] = debit_by_account.get(tax_acc, ZERO) + tax

    grand = _q2(net_total + tax_total)
    bill.net_total = _q2(net_total)
    bill.tax_total = _q2(tax_total)
    bill.grand_total = grand

    lines = [
        LineInput(account=acc, debit=_q2(amt), currency=bill.currency, fx_rate=bill.fx_rate)
        for acc, amt in debit_by_account.items()
    ]
    lines.append(LineInput(
        account=get_account(order.company, "2110"), credit=grand,
        currency=bill.currency, fx_rate=bill.fx_rate, party=bill.party,
        description=f"AP {bill.party.name}",
    ))
    entry = post_entry(EntryInput(
        company=order.company, date=order.date,
        memo=f"Supplier bill {bill.number or bill.pk}",
        source_type="supplier_bill", source_id=bill.pk, lines=lines,
    ))
    bill.journal_entry = entry
    bill.save()
    order.status = DocumentStatus.INVOICED
    order.save(update_fields=["status"])
    return bill


# --------------------------------------------------------------------------- #
# Settlement
# --------------------------------------------------------------------------- #
@transaction.atomic
def register_payment(payment: Payment):
    """Post a payment and update the related invoice/bill paid amount."""
    cash = get_account(payment.company, payment.cash_account_code)
    if payment.direction == Payment.Direction.INBOUND:
        ar = get_account(payment.company, "1130")
        entry = post_entry(EntryInput(
            company=payment.company, date=payment.date,
            memo=f"Customer receipt {payment.party.name}",
            source_type="payment", source_id=payment.pk,
            lines=[
                LineInput(account=cash, debit=payment.amount, currency=payment.currency, fx_rate=payment.fx_rate),
                LineInput(account=ar, credit=payment.amount, currency=payment.currency, fx_rate=payment.fx_rate, party=payment.party),
            ],
        ))
        if payment.customer_invoice:
            inv = payment.customer_invoice
            inv.amount_paid = _q2(inv.amount_paid + payment.amount)
            inv.save(update_fields=["amount_paid"])
    else:
        ap = get_account(payment.company, "2110")
        entry = post_entry(EntryInput(
            company=payment.company, date=payment.date,
            memo=f"Supplier payment {payment.party.name}",
            source_type="payment", source_id=payment.pk,
            lines=[
                LineInput(account=ap, debit=payment.amount, currency=payment.currency, fx_rate=payment.fx_rate, party=payment.party),
                LineInput(account=cash, credit=payment.amount, currency=payment.currency, fx_rate=payment.fx_rate),
            ],
        ))
        if payment.supplier_bill:
            bill = payment.supplier_bill
            bill.amount_paid = _q2(bill.amount_paid + payment.amount)
            bill.save(update_fields=["amount_paid"])
    payment.journal_entry = entry
    payment.save(update_fields=["journal_entry"])
    return payment
