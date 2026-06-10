from datetime import date, timedelta
from decimal import Decimal

from django.test import TestCase

from apps.accounting.chart_of_accounts import seed_chart_of_accounts
from apps.core.models import Company, Currency
from apps.masterdata.models import Party
from apps.orders.models import Payment

from .models import BankAccount, BankStatementLine
from .services import auto_match, import_statement_csv, match_manually

CSV = """date,description,amount
2026-06-01,Customer transfer ACME,525.00
2026-06-02,Supplier payment GLOBAL,-420.00
2026-06-03,Unknown card fee,-9.99
"""


class BankReconciliationTests(TestCase):
    def setUp(self):
        cur = Currency.objects.create(code="AED", name="Dirham")
        self.company = Company.objects.create(name="Gulf", country_code="AE", base_currency=cur)
        seed_chart_of_accounts(self.company)
        self.bank = BankAccount.objects.create(company=self.company, name="Main AED", currency=cur)
        cust = Party.objects.create(company=self.company, name="Acme", is_customer=True)
        supp = Party.objects.create(company=self.company, name="Global", is_supplier=True)
        self.p_in = Payment.objects.create(
            company=self.company, party=cust, direction=Payment.Direction.INBOUND,
            date=date(2026, 6, 1), currency=cur, amount=Decimal("525.00"),
            approval_status=Payment.Approval.APPROVED,
        )
        self.p_out = Payment.objects.create(
            company=self.company, party=supp, direction=Payment.Direction.OUTBOUND,
            date=date(2026, 6, 3), currency=cur, amount=Decimal("420.00"),
            approval_status=Payment.Approval.APPROVED,
        )

    def test_import_and_auto_match(self):
        statement = import_statement_csv(self.bank, CSV, date(2026, 6, 30), reference="JUN")
        self.assertEqual(statement.lines.count(), 3)
        result = auto_match(statement)
        # The 525 in and 420 out match; the card fee stays unmatched.
        self.assertEqual(result, {"matched": 2, "unmatched": 1})
        line_in = statement.lines.get(amount=Decimal("525.00"))
        self.assertEqual(line_in.matched_payment, self.p_in)
        line_out = statement.lines.get(amount=Decimal("-420.00"))
        self.assertEqual(line_out.matched_payment, self.p_out)

    def test_payment_not_matched_twice(self):
        statement = import_statement_csv(
            self.bank,
            "2026-06-01,first,525.00\n2026-06-01,duplicate,525.00\n",
            date(2026, 6, 30),
        )
        result = auto_match(statement)
        self.assertEqual(result["matched"], 1)  # only one line claims the payment

    def test_date_tolerance(self):
        far = self.p_in.date + timedelta(days=30)
        statement = import_statement_csv(self.bank, f"{far},late transfer,525.00\n", date(2026, 7, 31))
        result = auto_match(statement)
        self.assertEqual(result["matched"], 0)  # outside the +/-5 day window

    def test_manual_match(self):
        statement = import_statement_csv(self.bank, "2026-06-20,odd reference,525.00\n", date(2026, 6, 30))
        line = statement.lines.first()
        match_manually(line, self.p_in)
        line.refresh_from_db()
        self.assertEqual(line.status, BankStatementLine.Status.MANUAL)
        self.assertEqual(line.matched_payment, self.p_in)
