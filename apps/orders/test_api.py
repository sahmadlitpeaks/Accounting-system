from datetime import date
from decimal import Decimal

from django.contrib.auth import get_user_model
from rest_framework.test import APITestCase

from apps.accounting.chart_of_accounts import seed_chart_of_accounts
from apps.accounting.services import get_account
from apps.core.models import Company, Currency
from apps.inventory.services import receive_stock
from apps.masterdata.models import Item, Party, TaxCode, UnitOfMeasure, Warehouse

User = get_user_model()


class SalesOrderApiTests(APITestCase):
    """The exact flow the frontend drives: create order -> deliver -> invoice."""

    def setUp(self):
        cur = Currency.objects.create(code="AED", name="Dirham")
        self.company = Company.objects.create(name="Gulf", country_code="AE",
                                              base_currency=cur, tax_registration_number="TRN1")
        seed_chart_of_accounts(self.company)
        self.tax = TaxCode.objects.create(company=self.company, name="VAT 5%", kind=TaxCode.Kind.VAT,
                                          rate=Decimal("5"),
                                          output_account=get_account(self.company, "2120"),
                                          input_account=get_account(self.company, "1150"))
        uom = UnitOfMeasure.objects.create(company=self.company, code="PCS", name="Pieces")
        self.wh = Warehouse.objects.create(company=self.company, code="MAIN", name="Main")
        self.item = Item.objects.create(company=self.company, sku="W1", name="Widget",
                                        uom=uom, sales_tax_code=self.tax)
        self.cust = Party.objects.create(company=self.company, name="Acme", is_customer=True, currency=cur)
        receive_stock(company=self.company, item=self.item, warehouse=self.wh,
                      quantity=10, unit_cost=Decimal("40"), date=date.today())
        self.user = User.objects.create_superuser("api-admin", password="x")
        self.client.force_authenticate(self.user)
        self.cur = cur

    def test_create_deliver_invoice_via_api(self):
        # Create with nested lines.
        resp = self.client.post("/api/orders/sales-orders/", {
            "company": self.company.id, "party": self.cust.id,
            "date": str(date.today()), "currency": self.cur.code,
            "warehouse": self.wh.id,
            "lines": [{"item": self.item.id, "quantity": "2", "unit_price": "100", "tax_code": self.tax.id}],
        }, format="json")
        self.assertEqual(resp.status_code, 201, resp.content)
        order_id = resp.data["id"]

        resp = self.client.post(f"/api/orders/sales-orders/{order_id}/deliver/")
        self.assertEqual(resp.status_code, 200, resp.content)

        with self.captureOnCommitCallbacks(execute=True):
            resp = self.client.post(f"/api/orders/sales-orders/{order_id}/invoice/", {}, format="json")
        self.assertEqual(resp.status_code, 201, resp.content)
        self.assertEqual(resp.data["grand_total"], "210.00")  # 200 + 5% VAT
        self.assertTrue(resp.data["number"].startswith("INV-"))

        # Invoice list reflects the cleared fiscal status; PDF endpoint serves.
        invoice_id = resp.data["id"]
        resp = self.client.get(f"/api/orders/customer-invoices/?company={self.company.id}")
        self.assertEqual(resp.data["results"][0]["fiscal_status"], "cleared")
        resp = self.client.get(f"/api/orders/customer-invoices/{invoice_id}/pdf/")
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp["Content-Type"], "application/pdf")

    def test_destructive_methods_blocked(self):
        resp = self.client.post("/api/orders/sales-orders/", {
            "company": self.company.id, "party": self.cust.id,
            "date": str(date.today()), "currency": self.cur.code,
            "warehouse": self.wh.id,
            "lines": [{"item": self.item.id, "quantity": "1", "unit_price": "50"}],
        }, format="json")
        order_id = resp.data["id"]
        self.assertEqual(self.client.delete(f"/api/orders/sales-orders/{order_id}/").status_code, 405)
        self.assertEqual(self.client.put(f"/api/orders/sales-orders/{order_id}/", {}).status_code, 405)
