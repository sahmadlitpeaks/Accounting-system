from datetime import date
from decimal import Decimal

from django.test import TestCase

from apps.core.models import Company, Currency

from .chart_of_accounts import seed_chart_of_accounts
from .models import AccountType, Account, AccountingPeriod, JournalEntry
from .services import (
    EntryInput,
    LineInput,
    PostingError,
    get_account,
    post_entry,
    reverse_entry,
    trial_balance,
)


class AccountingCoreTests(TestCase):
    def setUp(self):
        self.aed = Currency.objects.create(code="AED", name="UAE Dirham", symbol="د.إ")
        self.company = Company.objects.create(
            name="Gulf Trading LLC", country_code="AE", base_currency=self.aed,
        )
        seed_chart_of_accounts(self.company)

    def test_seed_creates_all_five_account_types(self):
        types = set(Account.objects.filter(company=self.company).values_list("type", flat=True))
        self.assertEqual(types, {t.value for t in AccountType})

    def test_normal_balance(self):
        self.assertEqual(get_account(self.company, "1110").normal_balance, "debit")   # asset
        self.assertEqual(get_account(self.company, "2110").normal_balance, "credit")  # liability
        self.assertEqual(get_account(self.company, "4100").normal_balance, "credit")  # income
        self.assertEqual(get_account(self.company, "5100").normal_balance, "debit")   # expense

    def test_balanced_entry_posts(self):
        entry = post_entry(EntryInput(
            company=self.company, date=date.today(), memo="cash sale",
            lines=[
                LineInput(account=get_account(self.company, "1120"), debit=Decimal("100")),
                LineInput(account=get_account(self.company, "4100"), credit=Decimal("100")),
            ],
        ))
        self.assertEqual(entry.status, JournalEntry.Status.POSTED)
        self.assertTrue(entry.is_balanced)
        self.assertEqual(entry.total_debit, Decimal("100.00"))

    def test_unbalanced_entry_rejected(self):
        with self.assertRaises(PostingError):
            post_entry(EntryInput(
                company=self.company, date=date.today(),
                lines=[
                    LineInput(account=get_account(self.company, "1120"), debit=Decimal("100")),
                    LineInput(account=get_account(self.company, "4100"), credit=Decimal("90")),
                ],
            ))
        self.assertEqual(JournalEntry.objects.count(), 0)  # atomic rollback

    def test_group_account_not_postable(self):
        with self.assertRaises(PostingError):
            post_entry(EntryInput(
                company=self.company, date=date.today(),
                lines=[
                    LineInput(account=get_account(self.company, "1000"), debit=Decimal("100")),
                    LineInput(account=get_account(self.company, "4100"), credit=Decimal("100")),
                ],
            ))

    def test_closed_period_rejected(self):
        AccountingPeriod.objects.create(
            company=self.company, name="closed", start_date=date(2020, 1, 1),
            end_date=date(2020, 12, 31), status=AccountingPeriod.Status.CLOSED,
        )
        with self.assertRaises(PostingError):
            post_entry(EntryInput(
                company=self.company, date=date(2020, 6, 1),
                lines=[
                    LineInput(account=get_account(self.company, "1120"), debit=Decimal("10")),
                    LineInput(account=get_account(self.company, "4100"), credit=Decimal("10")),
                ],
            ))

    def test_reverse_entry_nets_to_zero(self):
        entry = post_entry(EntryInput(
            company=self.company, date=date.today(),
            lines=[
                LineInput(account=get_account(self.company, "1120"), debit=Decimal("50")),
                LineInput(account=get_account(self.company, "4100"), credit=Decimal("50")),
            ],
        ))
        reverse_entry(entry)
        tb = {row["code"]: row["balance"] for row in trial_balance(self.company)}
        self.assertEqual(tb.get("1120", Decimal("0")), Decimal("0.00"))
        self.assertEqual(tb.get("4100", Decimal("0")), Decimal("0.00"))

    def test_trial_balance_balances(self):
        post_entry(EntryInput(
            company=self.company, date=date.today(),
            lines=[
                LineInput(account=get_account(self.company, "1130"), debit=Decimal("210")),
                LineInput(account=get_account(self.company, "4100"), credit=Decimal("200")),
                LineInput(account=get_account(self.company, "2120"), credit=Decimal("10")),
            ],
        ))
        rows = trial_balance(self.company)
        total_debit = sum(r["debit"] for r in rows)
        total_credit = sum(r["credit"] for r in rows)
        self.assertEqual(total_debit, total_credit)
