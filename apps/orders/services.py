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
from apps.core.sequences import next_number
from apps.inventory.services import issue_stock, receive_stock
from apps.masterdata.models import Item
from apps.tax.services import line_tax

from .models import (
    ZERO,
    CustomerCreditNote,
    CustomerCreditNoteLine,
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
        number=number or next_number(order.company, "customer_invoice", order.date),
        status=DocumentStatus.CONFIRMED,
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
def bill_purchase_order(order: PurchaseOrder, number: str = "", withholding_tax_code=None) -> SupplierBill:
    """Create a supplier bill: clear GRNI for stock, expense services, add input
    tax, deduct any withholding tax, credit AP.

      Dr 2140/5xxx (net) + Dr 1150 (input tax)
      Cr 2110 AP (net + tax - WHT)  +  Cr 2130 WHT payable (WHT)
    """
    bill = SupplierBill.objects.create(
        company=order.company, party=order.party, purchase_order=order,
        date=order.date, currency=order.currency, fx_rate=order.fx_rate,
        number=number or next_number(order.company, "supplier_bill", order.date),
        withholding_tax_code=withholding_tax_code, status=DocumentStatus.CONFIRMED,
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
        code = "2140" if line.item.kind == Item.Kind.STOCK else "5240"
        acc = get_account(order.company, code)
        debit_by_account[acc] = debit_by_account.get(acc, ZERO) + net
        if tax > 0:
            tax_acc = (line.tax_code.input_account_id and line.tax_code.input_account) or get_account(order.company, "1150")
            debit_by_account[tax_acc] = debit_by_account.get(tax_acc, ZERO) + tax

    # Withholding tax is computed on the net (tax-exclusive) amount.
    wht = line_tax(net_total, withholding_tax_code) if withholding_tax_code else ZERO
    grand = _q2(net_total + tax_total)
    bill.net_total = _q2(net_total)
    bill.tax_total = _q2(tax_total)
    bill.withholding_total = _q2(wht)
    bill.grand_total = grand

    lines = [
        LineInput(account=acc, debit=_q2(amt), currency=bill.currency, fx_rate=bill.fx_rate)
        for acc, amt in debit_by_account.items()
    ]
    if wht > 0:
        lines.append(LineInput(
            account=get_account(order.company, "2130"), credit=_q2(wht),
            currency=bill.currency, fx_rate=bill.fx_rate,
            description="Withholding tax payable",
        ))
    lines.append(LineInput(
        account=get_account(order.company, "2110"), credit=_q2(grand - wht),
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
# Credit notes (sales returns / corrections)
# --------------------------------------------------------------------------- #
@transaction.atomic
def create_credit_note(invoice: CustomerInvoice, lines=None, reason: str = "",
                       restock: bool = True, number: str = "") -> CustomerCreditNote:
    """Issue a credit note against ``invoice``. Reverses revenue/output-tax/AR,
    optionally restocks returned goods, and fiscalizes the credit note.

    ``lines`` may be a list of dicts {item, quantity, unit_price, tax_code} for a
    partial credit; if omitted, every invoice line is fully credited.
    """
    cn = CustomerCreditNote.objects.create(
        company=invoice.company, party=invoice.party, invoice=invoice,
        date=invoice.date, currency=invoice.currency, fx_rate=invoice.fx_rate,
        number=number or next_number(invoice.company, "customer_credit_note", invoice.date),
        reason=reason, restock=restock, status=DocumentStatus.CONFIRMED,
    )

    if lines is None:
        source = [
            {"item": ln.item, "quantity": ln.quantity, "unit_price": ln.unit_price, "tax_code": ln.tax_code}
            for ln in invoice.lines.select_related("item", "tax_code")
        ]
    else:
        source = lines

    net_total = ZERO
    tax_total = ZERO
    revenue_by_code: dict = {}
    tax_by_account: dict = {}
    restock_cost = ZERO

    for ln in source:
        net = _q2(ln["quantity"] * ln["unit_price"])
        tax_code = ln.get("tax_code")
        tax = line_tax(net, tax_code)
        CustomerCreditNoteLine.objects.create(
            credit_note=cn, item=ln["item"], description=ln["item"].name,
            quantity=ln["quantity"], unit_price=ln["unit_price"],
            tax_code=tax_code, net_amount=net, tax_amount=tax,
        )
        net_total += net
        tax_total += tax
        rev_code = _revenue_code(ln["item"])
        revenue_by_code[rev_code] = revenue_by_code.get(rev_code, ZERO) + net
        if tax > 0:
            tax_acc = (tax_code.output_account_id and tax_code.output_account) or get_account(invoice.company, "2120")
            tax_by_account[tax_acc] = tax_by_account.get(tax_acc, ZERO) + tax
        if restock and ln["item"].kind == Item.Kind.STOCK:
            cost = _q2(ln["quantity"] * ln["item"].standard_cost)
            if cost > 0 and invoice.sales_order and invoice.sales_order.warehouse:
                receive_stock(
                    company=invoice.company, item=ln["item"],
                    warehouse=invoice.sales_order.warehouse,
                    quantity=ln["quantity"], unit_cost=ln["item"].standard_cost,
                    date=invoice.date, source_type="customer_credit_note", source_id=cn.pk,
                )
                restock_cost += cost

    grand = _q2(net_total + tax_total)
    cn.net_total = _q2(net_total)
    cn.tax_total = _q2(tax_total)
    cn.grand_total = grand

    # Reverse the original sale: Dr Revenue + Dr Output tax / Cr AR.
    gl_lines = [LineInput(
        account=get_account(invoice.company, code), debit=_q2(amount),
        currency=cn.currency, fx_rate=cn.fx_rate,
    ) for code, amount in revenue_by_code.items()]
    for tax_acc, amount in tax_by_account.items():
        gl_lines.append(LineInput(account=tax_acc, debit=_q2(amount), currency=cn.currency, fx_rate=cn.fx_rate))
    gl_lines.append(LineInput(
        account=get_account(invoice.company, "1130"), credit=grand,
        currency=cn.currency, fx_rate=cn.fx_rate, party=cn.party,
        description=f"Credit note {cn.number}",
    ))
    entry = post_entry(EntryInput(
        company=invoice.company, date=cn.date,
        memo=f"Credit note {cn.number} (inv {invoice.number})",
        source_type="customer_credit_note", source_id=cn.pk, lines=gl_lines,
    ))
    cn.journal_entry = entry
    cn.save()

    # Restock returned goods back into inventory at standard cost: Dr 1140 / Cr 5100.
    if restock_cost > 0:
        post_entry(EntryInput(
            company=invoice.company, date=cn.date,
            memo=f"Restock for credit note {cn.number}",
            source_type="customer_credit_note", source_id=cn.pk,
            lines=[
                LineInput(account=get_account(invoice.company, "1140"), debit=restock_cost),
                LineInput(account=get_account(invoice.company, "5100"), credit=restock_cost),
            ],
        ))

    from apps.compliance.services import submit_document
    submit_document(cn, "customer_credit_note")
    return cn


# --------------------------------------------------------------------------- #
# Settlement
# --------------------------------------------------------------------------- #
def create_payment_request(*, company, party, direction, date, currency, amount,
                           created_by, cash_account_code="1120", customer_invoice=None,
                           supplier_bill=None, fx_rate=Decimal("1")) -> Payment:
    """Maker step: record a payment awaiting approval. Does NOT post to the GL."""
    from apps.accounts.access import require

    require(created_by, company, "create_payment")
    return Payment.objects.create(
        company=company, party=party, direction=direction, date=date,
        currency=currency, fx_rate=fx_rate, amount=amount,
        cash_account_code=cash_account_code, customer_invoice=customer_invoice,
        supplier_bill=supplier_bill, created_by=created_by,
        approval_status=Payment.Approval.DRAFT,
    )


@transaction.atomic
def approve_payment(payment: Payment, approver) -> Payment:
    """Checker step: a *different* user with approval rights posts the payment.
    Enforces segregation of duties."""
    from apps.accounts.access import PermissionDenied, require

    if payment.approval_status == Payment.Approval.APPROVED:
        raise OrderError("Payment is already approved.")
    require(approver, payment.company, "approve_payment")
    if payment.created_by_id and approver.id == payment.created_by_id:
        raise PermissionDenied("The approver must be different from the payment creator.")

    payment.approved_by = approver
    payment.approval_status = Payment.Approval.APPROVED
    payment.save(update_fields=["approved_by", "approval_status"])
    register_payment(payment)
    return payment


def reject_payment(payment: Payment, approver, reason: str = "") -> Payment:
    payment.approval_status = Payment.Approval.REJECTED
    payment.approved_by = approver
    payment.save(update_fields=["approval_status", "approved_by"])
    return payment


def _fx_diff_line(company, base_debits: Decimal, base_credits: Decimal):
    """Return the gain/loss LineInput that balances an FX-affected entry.

    Debit excess -> credit 4900 FX gain; credit excess -> debit 5900 FX loss.
    """
    diff = _q2(base_debits - base_credits)
    if diff > 0:
        return LineInput(account=get_account(company, "4900"), credit=diff,
                         description="Realised FX gain")
    if diff < 0:
        return LineInput(account=get_account(company, "5900"), debit=-diff,
                         description="Realised FX loss")
    return None


@transaction.atomic
def register_payment(payment: Payment):
    """Post a payment and update the related invoice/bill paid amount."""
    cash = get_account(payment.company, payment.cash_account_code)
    if payment.direction == Payment.Direction.INBOUND:
        ar = get_account(payment.company, "1130")
        # Settle AR at the rate it was booked at (the invoice rate) so the
        # base-currency receivable nets to zero; the difference between that and
        # the payment-date rate is a realised FX gain/loss.
        ar_rate = payment.customer_invoice.fx_rate if payment.customer_invoice else payment.fx_rate
        lines = [
            LineInput(account=cash, debit=payment.amount, currency=payment.currency, fx_rate=payment.fx_rate),
            LineInput(account=ar, credit=payment.amount, currency=payment.currency, fx_rate=ar_rate, party=payment.party),
        ]
        if payment.currency_id != payment.company.base_currency_id:
            fx = _fx_diff_line(payment.company,
                               _q2(payment.amount * payment.fx_rate),
                               _q2(payment.amount * ar_rate))
            if fx:
                lines.append(fx)
        entry = post_entry(EntryInput(
            company=payment.company, date=payment.date,
            memo=f"Customer receipt {payment.party.name}",
            source_type="payment", source_id=payment.pk, lines=lines,
        ))
        if payment.customer_invoice:
            inv = payment.customer_invoice
            inv.amount_paid = _q2(inv.amount_paid + payment.amount)
            inv.save(update_fields=["amount_paid"])
    else:
        ap = get_account(payment.company, "2110")
        ap_rate = payment.supplier_bill.fx_rate if payment.supplier_bill else payment.fx_rate
        lines = [
            LineInput(account=ap, debit=payment.amount, currency=payment.currency, fx_rate=ap_rate, party=payment.party),
            LineInput(account=cash, credit=payment.amount, currency=payment.currency, fx_rate=payment.fx_rate),
        ]
        if payment.currency_id != payment.company.base_currency_id:
            fx = _fx_diff_line(payment.company,
                               _q2(payment.amount * ap_rate),
                               _q2(payment.amount * payment.fx_rate))
            if fx:
                lines.append(fx)
        entry = post_entry(EntryInput(
            company=payment.company, date=payment.date,
            memo=f"Supplier payment {payment.party.name}",
            source_type="payment", source_id=payment.pk, lines=lines,
        ))
        if payment.supplier_bill:
            bill = payment.supplier_bill
            bill.amount_paid = _q2(bill.amount_paid + payment.amount)
            bill.save(update_fields=["amount_paid"])
    payment.journal_entry = entry
    payment.save(update_fields=["journal_entry"])
    return payment
