from datetime import date
from decimal import Decimal

from django.test import TestCase

from apps.accounting.chart_of_accounts import seed_chart_of_accounts
from apps.accounting.models import JournalEntry
from apps.accounting.services import trial_balance
from apps.core.models import Company, Currency
from apps.inventory.services import receive_stock, stock_on_hand
from apps.masterdata.models import Item, Party, TaxCode, UnitOfMeasure, Warehouse

from .models import CustomerInvoice, FiscalStatus, Payment, PurchaseOrder, PurchaseOrderLine, SalesOrder, SalesOrderLine
from .services import (
    bill_purchase_order,
    deliver_sales_order,
    invoice_sales_order,
    receive_purchase_order,
    register_payment,
)


def _company(name, country, code, rate, kind):
    cur = Currency.objects.create(code=code, name=name)
    company = Company.objects.create(name=name, country_code=country, base_currency=cur, tax_registration_number="TRN1")
    seed_chart_of_accounts(company)
    from apps.accounting.services import get_account
    tax = TaxCode.objects.create(
        company=company, name=f"{country} tax", kind=kind, rate=rate,
        output_account=get_account(company, "2120"), input_account=get_account(company, "1150"),
    )
    uom = UnitOfMeasure.objects.create(company=company, code="PCS", name="Pieces")
    wh = Warehouse.objects.create(company=company, code="MAIN", name="Main")
    item = Item.objects.create(company=company, sku="W1", name="Widget", uom=uom, sales_tax_code=tax)
    customer = Party.objects.create(company=company, name="Cust", is_customer=True, currency=cur)
    supplier = Party.objects.create(company=company, name="Supp", is_supplier=True, currency=cur)
    return dict(company=company, cur=cur, tax=tax, item=item, wh=wh, customer=customer, supplier=supplier)


def _balanced(company):
    rows = trial_balance(company)
    return sum(r["debit"] for r in rows) == sum(r["credit"] for r in rows)


class SalesFlowTests(TestCase):
    """UAE company: full order-to-cash with 5% VAT and e-invoicing."""

    def setUp(self):
        self.ctx = _company("Gulf Trading", "AE", "AED", Decimal("5"), TaxCode.Kind.VAT)

    def test_order_to_cash(self):
        ctx = self.ctx
        # Stock on hand so delivery can issue.
        receive_stock(company=ctx["company"], item=ctx["item"], warehouse=ctx["wh"],
                      quantity=10, unit_cost=Decimal("40"), date=date.today())

        so = SalesOrder.objects.create(company=ctx["company"], party=ctx["customer"],
                                       date=date.today(), currency=ctx["cur"], warehouse=ctx["wh"])
        SalesOrderLine.objects.create(order=so, item=ctx["item"], quantity=Decimal("5"),
                                      unit_price=Decimal("100"), tax_code=ctx["tax"])

        deliver_sales_order(so)
        self.assertEqual(stock_on_hand(ctx["item"]), Decimal("5.0000"))

        with self.captureOnCommitCallbacks(execute=True):
            invoice = invoice_sales_order(so, number="INV-001")
        invoice.refresh_from_db()
        # 5 * 100 = 500 net; 5% VAT = 25; gross 525.
        self.assertEqual(invoice.net_total, Decimal("500.00"))
        self.assertEqual(invoice.tax_total, Decimal("25.00"))
        self.assertEqual(invoice.grand_total, Decimal("525.00"))
        # e-invoicing ran (eager) -> cleared with a UAE peppol id.
        self.assertEqual(invoice.fiscal_status, FiscalStatus.CLEARED)
        self.assertTrue(invoice.peppol_id)
        self.assertTrue(_balanced(ctx["company"]))

        # Customer pays in full.
        pay = Payment.objects.create(company=ctx["company"], party=ctx["customer"],
                                     direction=Payment.Direction.INBOUND, date=date.today(),
                                     currency=ctx["cur"], amount=Decimal("525"),
                                     customer_invoice=invoice)
        register_payment(pay)
        invoice.refresh_from_db()
        self.assertEqual(invoice.amount_due, Decimal("0.00"))
        self.assertTrue(_balanced(ctx["company"]))


class PakistanComplianceTests(TestCase):
    """Pakistan company: invoice clears via the FBR adapter (number + QR)."""

    def setUp(self):
        self.ctx = _company("Lahore Traders", "PK", "PKR", Decimal("18"), TaxCode.Kind.SALES)

    def test_invoice_gets_fbr_number(self):
        ctx = self.ctx
        receive_stock(company=ctx["company"], item=ctx["item"], warehouse=ctx["wh"],
                      quantity=10, unit_cost=Decimal("40"), date=date.today())
        so = SalesOrder.objects.create(company=ctx["company"], party=ctx["customer"],
                                       date=date.today(), currency=ctx["cur"], warehouse=ctx["wh"])
        SalesOrderLine.objects.create(order=so, item=ctx["item"], quantity=Decimal("1"),
                                      unit_price=Decimal("1000"), tax_code=ctx["tax"])
        deliver_sales_order(so)
        with self.captureOnCommitCallbacks(execute=True):
            invoice = invoice_sales_order(so, number="PK-001")
        invoice.refresh_from_db()
        self.assertEqual(invoice.tax_total, Decimal("180.00"))  # 18% of 1000
        self.assertEqual(invoice.fiscal_status, FiscalStatus.CLEARED)
        self.assertTrue(invoice.fbr_invoice_number.startswith("FBR"))
        self.assertTrue(invoice.qr_payload)


class PurchaseFlowTests(TestCase):
    def setUp(self):
        self.ctx = _company("Gulf Trading", "AE", "AED", Decimal("5"), TaxCode.Kind.VAT)

    def test_procure_to_pay(self):
        ctx = self.ctx
        po = PurchaseOrder.objects.create(company=ctx["company"], party=ctx["supplier"],
                                          date=date.today(), currency=ctx["cur"], warehouse=ctx["wh"])
        PurchaseOrderLine.objects.create(order=po, item=ctx["item"], quantity=Decimal("10"),
                                         unit_price=Decimal("40"), tax_code=ctx["tax"])
        receive_purchase_order(po)
        self.assertEqual(stock_on_hand(ctx["item"]), Decimal("10.0000"))

        bill = bill_purchase_order(po, number="BILL-1")
        # 10 * 40 = 400 net; 5% = 20; gross 420.
        self.assertEqual(bill.grand_total, Decimal("420.00"))
        self.assertTrue(_balanced(ctx["company"]))

        pay = Payment.objects.create(company=ctx["company"], party=ctx["supplier"],
                                     direction=Payment.Direction.OUTBOUND, date=date.today(),
                                     currency=ctx["cur"], amount=Decimal("420"),
                                     supplier_bill=bill)
        register_payment(pay)
        bill.refresh_from_db()
        self.assertEqual(bill.amount_due, Decimal("0.00"))
        self.assertTrue(_balanced(ctx["company"]))
