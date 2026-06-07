from datetime import date
from decimal import Decimal

from django.test import TestCase

from apps.core.models import Company, Currency

from .chart_of_accounts import seed_chart_of_accounts
from .reports import balance_sheet, profit_and_loss
from .services import EntryInput, LineInput, get_account, post_entry


class FinancialStatementTests(TestCase):
    def setUp(self):
        self.cur = Currency.objects.create(code="AED", name="Dirham")
        self.company = Company.objects.create(name="Gulf", country_code="AE", base_currency=self.cur)
        seed_chart_of_accounts(self.company)

        # A cash sale of 1000 and an expense of 300, so net profit = 700.
        post_entry(EntryInput(company=self.company, date=date.today(), lines=[
            LineInput(account=get_account(self.company, "1120"), debit=Decimal("1000")),
            LineInput(account=get_account(self.company, "4100"), credit=Decimal("1000")),
        ]))
        post_entry(EntryInput(company=self.company, date=date.today(), lines=[
            LineInput(account=get_account(self.company, "5220"), debit=Decimal("300")),
            LineInput(account=get_account(self.company, "1120"), credit=Decimal("300")),
        ]))

    def test_profit_and_loss(self):
        pnl = profit_and_loss(self.company)
        self.assertEqual(pnl["total_income"], Decimal("1000"))
        self.assertEqual(pnl["total_expense"], Decimal("300"))
        self.assertEqual(pnl["net_profit"], Decimal("700"))

    def test_balance_sheet_balances(self):
        bs = balance_sheet(self.company)
        # Cash 1000 - 300 = 700 in assets; equity 0 + current result 700.
        self.assertEqual(bs["total_assets"], Decimal("700"))
        self.assertEqual(bs["current_year_result"], Decimal("700"))
        self.assertEqual(bs["total_equity_and_liabilities"], Decimal("700"))
        self.assertTrue(bs["balances"])
