from datetime import date
from decimal import Decimal

from django.test import TestCase

from apps.accounting.chart_of_accounts import seed_chart_of_accounts
from apps.accounting.services import get_account
from apps.core.models import Company, Currency
from apps.inventory.services import receive_stock
from apps.masterdata.models import Item, Party, TaxCode, UnitOfMeasure, Warehouse

from .models import SalesOrder, SalesOrderLine
from .pdf import render_invoice_pdf
from .services import deliver_sales_order, invoice_sales_order


class InvoicePdfTests(TestCase):
    def setUp(self):
        cur = Currency.objects.create(code="PKR", name="Rupee")
        self.company = Company.objects.create(name="Lahore Traders", country_code="PK",
                                              base_currency=cur, tax_registration_number="1234567-8")
        seed_chart_of_accounts(self.company)
        tax = TaxCode.objects.create(company=self.company, name="GST", kind=TaxCode.Kind.SALES, rate=Decimal("18"),
                                     output_account=get_account(self.company, "2120"),
                                     input_account=get_account(self.company, "1150"))
        uom = UnitOfMeasure.objects.create(company=self.company, code="PCS", name="Pieces")
        wh = Warehouse.objects.create(company=self.company, code="MAIN", name="Main")
        item = Item.objects.create(company=self.company, sku="W1", name="Widget", uom=uom,
                                   sales_tax_code=tax, standard_cost=Decimal("40"))
        cust = Party.objects.create(company=self.company, name="Acme", is_customer=True, currency=cur,
                                    tax_registration_number="7654321-0")
        receive_stock(company=self.company, item=item, warehouse=wh, quantity=10, unit_cost=Decimal("40"), date=date.today())
        so = SalesOrder.objects.create(company=self.company, party=cust, date=date.today(), currency=cur, warehouse=wh)
        SalesOrderLine.objects.create(order=so, item=item, quantity=Decimal("2"), unit_price=Decimal("100"), tax_code=tax)
        deliver_sales_order(so)
        with self.captureOnCommitCallbacks(execute=True):
            self.invoice = invoice_sales_order(so)
        self.invoice.refresh_from_db()

    def test_pdf_bytes_produced_with_qr(self):
        content = render_invoice_pdf(self.invoice)
        self.assertTrue(content.startswith(b"%PDF"))
        self.assertGreater(len(content), 1500)  # has tables + embedded QR image
        # The invoice cleared via FBR, so it carries a fiscal reference for the QR.
        self.assertTrue(self.invoice.fbr_invoice_number)
