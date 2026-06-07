from datetime import date
from decimal import Decimal

from django.test import TestCase

from apps.accounting.chart_of_accounts import seed_chart_of_accounts
from apps.accounting.services import get_account, trial_balance
from apps.core.models import Company, Currency
from apps.core.sequences import next_number
from apps.inventory.services import receive_stock, stock_on_hand
from apps.masterdata.models import Item, Party, TaxCode, UnitOfMeasure, Warehouse

from .models import (
    CustomerCreditNote,
    FiscalStatus,
    PurchaseOrder,
    PurchaseOrderLine,
    SalesOrder,
    SalesOrderLine,
)
from .services import (
    bill_purchase_order,
    create_credit_note,
    deliver_sales_order,
    invoice_sales_order,
    receive_purchase_order,
)


def _ctx(country="PK", code="PKR"):
    cur = Currency.objects.create(code=code, name=code)
    company = Company.objects.create(name=f"{country} Co", country_code=country, base_currency=cur, tax_registration_number="T1")
    seed_chart_of_accounts(company)
    sales = TaxCode.objects.create(company=company, name="Sales", kind=TaxCode.Kind.SALES, rate=Decimal("18"),
                                   output_account=get_account(company, "2120"), input_account=get_account(company, "1150"))
    wht = TaxCode.objects.create(company=company, name="WHT", kind=TaxCode.Kind.WITHHOLDING, rate=Decimal("4"))
    uom = UnitOfMeasure.objects.create(company=company, code="PCS", name="Pieces")
    wh = Warehouse.objects.create(company=company, code="MAIN", name="Main")
    item = Item.objects.create(company=company, sku="W1", name="Widget", uom=uom, sales_tax_code=sales, standard_cost=Decimal("40"))
    cust = Party.objects.create(company=company, name="Cust", is_customer=True, currency=cur)
    supp = Party.objects.create(company=company, name="Supp", is_supplier=True, currency=cur)
    return dict(company=company, cur=cur, sales=sales, wht=wht, item=item, wh=wh, cust=cust, supp=supp)


def _balanced(company):
    rows = trial_balance(company)
    return sum(r["debit"] for r in rows) == sum(r["credit"] for r in rows)


class NumberingTests(TestCase):
    def setUp(self):
        self.ctx = _ctx()

    def test_sequence_is_gapless_and_formatted(self):
        c = self.ctx["company"]
        n1 = next_number(c, "customer_invoice", date(2026, 6, 1))
        n2 = next_number(c, "customer_invoice", date(2026, 6, 2))
        self.assertEqual(n1, "INV-2026-000001")
        self.assertEqual(n2, "INV-2026-000002")
        # New year resets.
        self.assertEqual(next_number(c, "customer_invoice", date(2027, 1, 1)), "INV-2027-000001")

    def test_invoice_auto_numbered(self):
        ctx = self.ctx
        receive_stock(company=ctx["company"], item=ctx["item"], warehouse=ctx["wh"], quantity=5, unit_cost=Decimal("40"), date=date.today())
        so = SalesOrder.objects.create(company=ctx["company"], party=ctx["cust"], date=date.today(), currency=ctx["cur"], warehouse=ctx["wh"])
        SalesOrderLine.objects.create(order=so, item=ctx["item"], quantity=Decimal("2"), unit_price=Decimal("100"), tax_code=ctx["sales"])
        deliver_sales_order(so)
        with self.captureOnCommitCallbacks(execute=True):
            inv = invoice_sales_order(so)
        self.assertTrue(inv.number.startswith("INV-"))


class WithholdingTaxTests(TestCase):
    def setUp(self):
        self.ctx = _ctx()

    def test_wht_reduces_payable_and_books_liability(self):
        ctx = self.ctx
        po = PurchaseOrder.objects.create(company=ctx["company"], party=ctx["supp"], date=date.today(), currency=ctx["cur"], warehouse=ctx["wh"])
        # service line so it expenses (no GRNI needed)
        svc = Item.objects.create(company=ctx["company"], sku="SVC", name="Service", uom=ctx["item"].uom, kind=Item.Kind.SERVICE)
        PurchaseOrderLine.objects.create(order=po, item=svc, quantity=Decimal("1"), unit_price=Decimal("1000"), tax_code=None)
        bill = bill_purchase_order(po, withholding_tax_code=ctx["wht"])
        # net 1000, no sales tax, WHT 4% = 40. Payable to supplier = 960.
        self.assertEqual(bill.withholding_total, Decimal("40.00"))
        self.assertEqual(bill.grand_total, Decimal("1000.00"))
        self.assertEqual(bill.amount_due, Decimal("960.00"))
        # WHT liability account 2130 has a 40 credit balance.
        tb = {r["code"]: r["balance"] for r in trial_balance(ctx["company"])}
        self.assertEqual(tb["2130"], Decimal("-40.00"))  # credit balance
        self.assertTrue(_balanced(ctx["company"]))


class CreditNoteTests(TestCase):
    def setUp(self):
        self.ctx = _ctx()

    def test_full_credit_note_reverses_and_restocks(self):
        ctx = self.ctx
        receive_stock(company=ctx["company"], item=ctx["item"], warehouse=ctx["wh"], quantity=10, unit_cost=Decimal("40"), date=date.today())
        so = SalesOrder.objects.create(company=ctx["company"], party=ctx["cust"], date=date.today(), currency=ctx["cur"], warehouse=ctx["wh"])
        SalesOrderLine.objects.create(order=so, item=ctx["item"], quantity=Decimal("3"), unit_price=Decimal("100"), tax_code=ctx["sales"])
        deliver_sales_order(so)
        with self.captureOnCommitCallbacks(execute=True):
            inv = invoice_sales_order(so)
        self.assertEqual(stock_on_hand(ctx["item"]), Decimal("7.0000"))

        with self.captureOnCommitCallbacks(execute=True):
            cn = create_credit_note(inv, reason="customer returned goods")
        cn.refresh_from_db()
        # 3 * 100 = 300 net, 18% = 54, gross 354.
        self.assertEqual(cn.net_total, Decimal("300.00"))
        self.assertEqual(cn.tax_total, Decimal("54.00"))
        self.assertEqual(cn.grand_total, Decimal("354.00"))
        # Goods restocked.
        self.assertEqual(stock_on_hand(ctx["item"]), Decimal("10.0000"))
        # Credit note fiscalized (FBR).
        self.assertEqual(cn.fiscal_status, FiscalStatus.CLEARED)
        self.assertTrue(cn.fbr_invoice_number)
        # Net AR across invoice + credit note is zero; books balanced.
        tb = {r["code"]: r["balance"] for r in trial_balance(ctx["company"])}
        self.assertEqual(tb.get("1130", Decimal("0")), Decimal("0.00"))
        self.assertTrue(_balanced(ctx["company"]))
