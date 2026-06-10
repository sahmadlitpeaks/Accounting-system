from datetime import date
from decimal import Decimal

from django.test import TestCase

from apps.accounting.chart_of_accounts import seed_chart_of_accounts
from apps.accounting.services import get_account
from apps.core.models import Company, Currency
from apps.inventory.services import receive_stock
from apps.masterdata.models import Item, Party, TaxCode, UnitOfMeasure, Warehouse
from apps.orders.models import PurchaseOrder, PurchaseOrderLine, SalesOrder, SalesOrderLine
from apps.orders.services import (
    bill_purchase_order,
    create_credit_note,
    deliver_sales_order,
    invoice_sales_order,
    receive_purchase_order,
)

from .reports import tax_return


class TaxReturnTests(TestCase):
    """Pakistan company: GST 18% on a sale, partial credit note, a purchase with
    input tax, and supplier WHT."""

    def setUp(self):
        cur = Currency.objects.create(code="PKR", name="Rupee")
        self.company = Company.objects.create(name="Lahore", country_code="PK", base_currency=cur, tax_registration_number="T1")
        seed_chart_of_accounts(self.company)
        self.gst = TaxCode.objects.create(company=self.company, name="GST 18%", kind=TaxCode.Kind.SALES, rate=Decimal("18"),
                                          output_account=get_account(self.company, "2120"),
                                          input_account=get_account(self.company, "1150"))
        self.wht = TaxCode.objects.create(company=self.company, name="WHT 4%", kind=TaxCode.Kind.WITHHOLDING, rate=Decimal("4"))
        uom = UnitOfMeasure.objects.create(company=self.company, code="PCS", name="Pieces")
        self.wh = Warehouse.objects.create(company=self.company, code="MAIN", name="Main")
        self.item = Item.objects.create(company=self.company, sku="W1", name="Widget", uom=uom,
                                        sales_tax_code=self.gst, standard_cost=Decimal("40"))
        self.cust = Party.objects.create(company=self.company, name="Cust", is_customer=True, currency=cur)
        self.supp = Party.objects.create(company=self.company, name="Supp", is_supplier=True, currency=cur)

    def test_tax_return_aggregates(self):
        cur = self.company.base_currency
        # Purchase: 10 @ 40 = 400 net, input tax 72, with 4% WHT (16).
        po = PurchaseOrder.objects.create(company=self.company, party=self.supp, date=date.today(),
                                          currency=cur, warehouse=self.wh)
        PurchaseOrderLine.objects.create(order=po, item=self.item, quantity=Decimal("10"),
                                         unit_price=Decimal("40"), tax_code=self.gst)
        receive_purchase_order(po)
        bill_purchase_order(po, withholding_tax_code=self.wht)

        # Sale: 5 @ 100 = 500 net, output tax 90.
        so = SalesOrder.objects.create(company=self.company, party=self.cust, date=date.today(),
                                       currency=cur, warehouse=self.wh)
        SalesOrderLine.objects.create(order=so, item=self.item, quantity=Decimal("5"),
                                      unit_price=Decimal("100"), tax_code=self.gst)
        deliver_sales_order(so)
        with self.captureOnCommitCallbacks(execute=True):
            invoice = invoice_sales_order(so)

        # Credit note for 1 unit: -100 net, -18 tax.
        with self.captureOnCommitCallbacks(execute=True):
            create_credit_note(invoice, lines=[{"item": self.item, "quantity": Decimal("1"),
                                                "unit_price": Decimal("100"), "tax_code": self.gst}],
                               restock=False)

        report = tax_return(self.company, date.today(), date.today())
        self.assertEqual(report["output_tax"], Decimal("72.00"))      # 90 - 18
        self.assertEqual(report["input_tax"], Decimal("72.00"))       # purchases
        self.assertEqual(report["net_tax_payable"], Decimal("0.00"))
        self.assertEqual(report["withholding_deducted"], Decimal("16.00"))
        self.assertEqual(report["sales"][0]["net"], Decimal("500.00"))
        self.assertEqual(report["credit_notes"][0]["tax"], Decimal("18.00"))
