from datetime import date
from decimal import Decimal

from django.test import TestCase

from apps.core.models import Company, Currency
from apps.masterdata.models import Item, UnitOfMeasure, Warehouse

from .services import InventoryError, issue_stock, receive_stock, stock_on_hand, stock_value


class InventoryValuationTests(TestCase):
    def setUp(self):
        self.cur = Currency.objects.create(code="PKR", name="Rupee")
        self.company = Company.objects.create(name="Lahore Traders", country_code="PK", base_currency=self.cur)
        self.uom = UnitOfMeasure.objects.create(company=self.company, code="PCS", name="Pieces")
        self.wh = Warehouse.objects.create(company=self.company, code="MAIN", name="Main")

    def _item(self, method):
        return Item.objects.create(
            company=self.company, sku=f"X-{method}", name="Item", uom=self.uom, valuation_method=method,
        )

    def test_fifo_cogs(self):
        item = self._item(Item.Valuation.FIFO)
        receive_stock(company=self.company, item=item, warehouse=self.wh, quantity=10, unit_cost=Decimal("4"), date=date.today())
        receive_stock(company=self.company, item=item, warehouse=self.wh, quantity=10, unit_cost=Decimal("6"), date=date.today())
        # Issue 15: 10@4 + 5@6 = 40 + 30 = 70
        _move, cogs = issue_stock(company=self.company, item=item, warehouse=self.wh, quantity=15, date=date.today())
        self.assertEqual(cogs, Decimal("70.00"))
        self.assertEqual(stock_on_hand(item), Decimal("5.0000"))
        self.assertEqual(stock_value(item), Decimal("30.00"))  # 5 @ 6

    def test_moving_average_cogs(self):
        item = self._item(Item.Valuation.MOVING_AVERAGE)
        receive_stock(company=self.company, item=item, warehouse=self.wh, quantity=10, unit_cost=Decimal("4"), date=date.today())
        receive_stock(company=self.company, item=item, warehouse=self.wh, quantity=10, unit_cost=Decimal("6"), date=date.today())
        # Average cost = (40 + 60) / 20 = 5. Issue 15 -> 75.
        _move, cogs = issue_stock(company=self.company, item=item, warehouse=self.wh, quantity=15, date=date.today())
        self.assertEqual(cogs, Decimal("75.00"))
        self.assertEqual(stock_on_hand(item), Decimal("5.0000"))
        self.assertEqual(stock_value(item), Decimal("25.00"))  # 5 @ 5

    def test_insufficient_stock_rejected(self):
        item = self._item(Item.Valuation.FIFO)
        receive_stock(company=self.company, item=item, warehouse=self.wh, quantity=2, unit_cost=Decimal("4"), date=date.today())
        with self.assertRaises(InventoryError):
            issue_stock(company=self.company, item=item, warehouse=self.wh, quantity=5, date=date.today())
