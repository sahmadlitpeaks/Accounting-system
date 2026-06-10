from datetime import date
from decimal import Decimal

from django.test import TestCase

from apps.accounting.chart_of_accounts import seed_chart_of_accounts
from apps.accounting.services import get_account, trial_balance
from apps.core.models import Company, Currency, ExchangeRate
from apps.inventory.services import receive_stock
from apps.masterdata.models import Item, Party, TaxCode, UnitOfMeasure, Warehouse

from .fx import revalue_open_documents
from .models import Payment, SalesOrder, SalesOrderLine
from .services import deliver_sales_order, invoice_sales_order, register_payment


class ForeignCurrencyTests(TestCase):
    """AED company invoicing in USD: realised FX on settlement, unrealised on
    revaluation."""

    def setUp(self):
        self.aed = Currency.objects.create(code="AED", name="Dirham")
        self.usd = Currency.objects.create(code="USD", name="US Dollar")
        self.company = Company.objects.create(name="Gulf", country_code="AE", base_currency=self.aed)
        seed_chart_of_accounts(self.company)
        tax = TaxCode.objects.create(company=self.company, name="VAT", kind=TaxCode.Kind.VAT, rate=Decimal("5"),
                                     output_account=get_account(self.company, "2120"),
                                     input_account=get_account(self.company, "1150"))
        uom = UnitOfMeasure.objects.create(company=self.company, code="PCS", name="Pieces")
        self.wh = Warehouse.objects.create(company=self.company, code="MAIN", name="Main")
        self.item = Item.objects.create(company=self.company, sku="W1", name="Widget", uom=uom, sales_tax_code=tax)
        self.cust = Party.objects.create(company=self.company, name="US Cust", is_customer=True, currency=self.usd)
        receive_stock(company=self.company, item=self.item, warehouse=self.wh,
                      quantity=10, unit_cost=Decimal("40"), date=date.today())
        self.tax = tax

    def _usd_invoice(self, rate):
        so = SalesOrder.objects.create(company=self.company, party=self.cust, date=date.today(),
                                       currency=self.usd, fx_rate=rate, warehouse=self.wh)
        SalesOrderLine.objects.create(order=so, item=self.item, quantity=Decimal("1"),
                                      unit_price=Decimal("100"), tax_code=self.tax)
        deliver_sales_order(so)
        with self.captureOnCommitCallbacks(execute=True):
            invoice = invoice_sales_order(so)
        invoice.refresh_from_db()
        return invoice

    def _tb(self):
        return {r["code"]: r["balance"] for r in trial_balance(self.company)}

    def test_realised_fx_gain_on_settlement(self):
        invoice = self._usd_invoice(Decimal("3.67"))
        # Gross 105 USD booked at 3.67 -> AR base 385.35.
        pay = Payment.objects.create(company=self.company, party=self.cust,
                                     direction=Payment.Direction.INBOUND, date=date.today(),
                                     currency=self.usd, fx_rate=Decimal("3.70"),
                                     amount=Decimal("105"), customer_invoice=invoice)
        register_payment(pay)
        tb = self._tb()
        # AR fully settled in base currency despite the rate difference.
        self.assertEqual(tb["1130"], Decimal("0.00"))
        # Gain = 105 * (3.70 - 3.67) = 3.15, credited to 4900 (credit balance).
        self.assertEqual(tb["4900"], Decimal("-3.15"))
        total_debit = sum(r["debit"] for r in trial_balance(self.company))
        total_credit = sum(r["credit"] for r in trial_balance(self.company))
        self.assertEqual(total_debit, total_credit)

    def test_realised_fx_loss_on_settlement(self):
        invoice = self._usd_invoice(Decimal("3.70"))
        pay = Payment.objects.create(company=self.company, party=self.cust,
                                     direction=Payment.Direction.INBOUND, date=date.today(),
                                     currency=self.usd, fx_rate=Decimal("3.65"),
                                     amount=Decimal("105"), customer_invoice=invoice)
        register_payment(pay)
        tb = self._tb()
        self.assertEqual(tb["1130"], Decimal("0.00"))
        # Loss = 105 * (3.70 - 3.65) = 5.25, debited to 5900.
        self.assertEqual(tb["5900"], Decimal("5.25"))

    def test_unrealised_revaluation_of_open_invoice(self):
        self._usd_invoice(Decimal("3.67"))  # stays unpaid
        ExchangeRate.objects.create(from_currency=self.usd, to_currency=self.aed,
                                    date=date.today(), rate=Decimal("3.80"))
        entry = revalue_open_documents(self.company, date.today())
        self.assertIsNotNone(entry)
        tb = self._tb()
        # Outstanding 105 USD: (3.80 - 3.67) * 105 = 13.65 unrealised gain.
        self.assertEqual(tb["4900"], Decimal("-13.65"))
        self.assertEqual(tb["1130"], Decimal("385.35") + Decimal("13.65"))

    def test_no_revaluation_when_nothing_open(self):
        self.assertIsNone(revalue_open_documents(self.company, date.today()))
