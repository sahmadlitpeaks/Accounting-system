from datetime import date
from decimal import Decimal

from django.core.exceptions import ValidationError
from django.test import TestCase

from apps.core.models import Company, Currency

from .chart_of_accounts import seed_chart_of_accounts
from .closing import close_period, close_year, reopen_period
from .models import AccountingPeriod, JournalEntry
from .reports import balance_sheet, profit_and_loss
from .services import EntryInput, LineInput, PostingError, get_account, post_entry, reverse_entry


class ImmutabilityTests(TestCase):
    def setUp(self):
        self.cur = Currency.objects.create(code="AED", name="Dirham")
        self.company = Company.objects.create(name="Gulf", country_code="AE", base_currency=self.cur)
        seed_chart_of_accounts(self.company)
        self.entry = post_entry(EntryInput(company=self.company, date=date.today(), lines=[
            LineInput(account=get_account(self.company, "1120"), debit=Decimal("100")),
            LineInput(account=get_account(self.company, "4100"), credit=Decimal("100")),
        ]))

    def test_posted_entry_cannot_be_edited(self):
        self.entry.memo = "tampered"
        with self.assertRaises(ValidationError):
            self.entry.save()

    def test_posted_entry_cannot_be_deleted(self):
        with self.assertRaises(ValidationError):
            self.entry.delete()

    def test_posted_line_cannot_be_deleted(self):
        line = self.entry.lines.first()
        with self.assertRaises(ValidationError):
            line.delete()

    def test_correction_is_via_reversal(self):
        reverse_entry(self.entry)
        # Two entries now exist; the reversal references the original.
        self.assertEqual(JournalEntry.objects.count(), 2)
        rev = JournalEntry.objects.get(reversal_of=self.entry)
        self.assertEqual(rev.total_debit, Decimal("100.00"))


class PeriodCloseTests(TestCase):
    def setUp(self):
        self.cur = Currency.objects.create(code="AED", name="Dirham")
        self.company = Company.objects.create(name="Gulf", country_code="AE", base_currency=self.cur)
        seed_chart_of_accounts(self.company)
        self.period = AccountingPeriod.objects.create(
            company=self.company, name="2026-06",
            start_date=date(2026, 6, 1), end_date=date(2026, 6, 30),
        )

    def test_cannot_post_into_closed_period(self):
        close_period(self.period)
        with self.assertRaises(PostingError):
            post_entry(EntryInput(company=self.company, date=date(2026, 6, 15), lines=[
                LineInput(account=get_account(self.company, "1120"), debit=Decimal("10")),
                LineInput(account=get_account(self.company, "4100"), credit=Decimal("10")),
            ]))
        reopen_period(self.period)
        # Reopened: posting now succeeds.
        post_entry(EntryInput(company=self.company, date=date(2026, 6, 15), lines=[
            LineInput(account=get_account(self.company, "1120"), debit=Decimal("10")),
            LineInput(account=get_account(self.company, "4100"), credit=Decimal("10")),
        ]))


class YearCloseTests(TestCase):
    def setUp(self):
        self.cur = Currency.objects.create(code="AED", name="Dirham")
        self.company = Company.objects.create(name="Gulf", country_code="AE", base_currency=self.cur)
        seed_chart_of_accounts(self.company)
        # Revenue 1000, expense 300 -> profit 700.
        post_entry(EntryInput(company=self.company, date=date(2026, 3, 1), lines=[
            LineInput(account=get_account(self.company, "1120"), debit=Decimal("1000")),
            LineInput(account=get_account(self.company, "4100"), credit=Decimal("1000")),
        ]))
        post_entry(EntryInput(company=self.company, date=date(2026, 4, 1), lines=[
            LineInput(account=get_account(self.company, "5220"), debit=Decimal("300")),
            LineInput(account=get_account(self.company, "1120"), credit=Decimal("300")),
        ]))

    def test_year_close_rolls_profit_into_retained_earnings(self):
        close_year(self.company, date(2026, 1, 1), date(2026, 12, 31))

        # Income & expense are zeroed for the year.
        pnl = profit_and_loss(self.company, start=date(2026, 1, 1), end=date(2026, 12, 31))
        self.assertEqual(pnl["total_income"], Decimal("0"))
        self.assertEqual(pnl["total_expense"], Decimal("0"))

        # Retained earnings now holds the 700 profit; balance sheet still balances.
        bs = balance_sheet(self.company, as_of=date(2026, 12, 31))
        retained = next((r["amount"] for r in bs["equity"] if r["code"] == "3200"), Decimal("0"))
        self.assertEqual(retained, Decimal("700"))
        self.assertTrue(bs["balances"])
