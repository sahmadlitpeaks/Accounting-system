from datetime import date
from decimal import Decimal

from django.test import TestCase

from apps.core.models import Company, Currency
from apps.inventory.services import issue_stock, stock_on_hand, stock_value
from apps.masterdata.models import Item, UnitOfMeasure, Warehouse

from .chart_of_accounts import seed_chart_of_accounts
from .opening import load_opening_balances, load_opening_stock
from .reports import balance_sheet
from .services import PostingError


class OpeningBalanceTests(TestCase):
    def setUp(self):
        cur = Currency.objects.create(code="PKR", name="Rupee")
        self.company = Company.objects.create(name="Lahore", country_code="PK", base_currency=cur)
        seed_chart_of_accounts(self.company)

    def test_balanced_opening_posts(self):
        entry = load_opening_balances(self.company, date(2026, 1, 1), [
            ("1120", "50000", "0"),   # bank
            ("1140", "20000", "0"),   # inventory value
            ("1130", "10000", "0"),   # receivables
            ("2110", "0", "15000"),   # payables
            ("3100", "0", "65000"),   # capital
        ])
        self.assertEqual(entry.lines.count(), 5)
        bs = balance_sheet(self.company, as_of=date(2026, 1, 1))
        self.assertEqual(bs["total_assets"], Decimal("80000"))
        self.assertTrue(bs["balances"])

    def test_unbalanced_opening_rejected(self):
        with self.assertRaises(PostingError):
            load_opening_balances(self.company, date(2026, 1, 1), [
                ("1120", "100", "0"),
                ("3100", "0", "90"),
            ])

    def test_opening_stock_loads_without_gl(self):
        uom = UnitOfMeasure.objects.create(company=self.company, code="PCS", name="Pieces")
        wh = Warehouse.objects.create(company=self.company, code="MAIN", name="Main")
        item = Item.objects.create(company=self.company, sku="W1", name="Widget", uom=uom)
        load_opening_stock(self.company, wh, date(2026, 1, 1), [(item, "100", "200")])
        self.assertEqual(stock_on_hand(item), Decimal("100"))
        self.assertEqual(stock_value(item), Decimal("20000.00"))
        # No GL was posted by the stock load itself.
        bs = balance_sheet(self.company)
        self.assertEqual(bs["total_assets"], Decimal("0"))
        # And the layers are consumable: issuing computes COGS from opening cost.
        _move, cogs = issue_stock(company=self.company, item=item, warehouse=wh,
                                  quantity=10, date=date(2026, 2, 1))
        self.assertEqual(cogs, Decimal("2000.00"))
