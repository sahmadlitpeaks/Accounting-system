from datetime import date
from decimal import Decimal

from django.test import TestCase

from apps.accounting.chart_of_accounts import seed_chart_of_accounts
from apps.accounting.services import trial_balance
from apps.core.models import Company, Currency

from .models import Employee, PayrollRun
from .services import PayrollError, pay_salaries, run_payroll


class PayrollTests(TestCase):
    """Pakistan company: salaries with flat income-tax withholding."""

    def setUp(self):
        cur = Currency.objects.create(code="PKR", name="Rupee")
        self.company = Company.objects.create(name="Lahore", country_code="PK", base_currency=cur)
        seed_chart_of_accounts(self.company)
        Employee.objects.create(company=self.company, name="Ali", basic_salary=Decimal("90000"),
                                allowances=Decimal("10000"), tax_rate=Decimal("5"))
        Employee.objects.create(company=self.company, name="Sara", basic_salary=Decimal("50000"),
                                tax_rate=Decimal("0"))

    def _tb(self):
        return {r["code"]: r["balance"] for r in trial_balance(self.company)}

    def test_run_payroll_posts_accrual(self):
        run = run_payroll(self.company, date(2026, 6, 30))
        # Ali: gross 100000, tax 5000, net 95000. Sara: 50000 net.
        self.assertEqual(run.gross_total, Decimal("150000.00"))
        self.assertEqual(run.tax_total, Decimal("5000.00"))
        self.assertEqual(run.net_total, Decimal("145000.00"))
        self.assertEqual(run.payslips.count(), 2)
        tb = self._tb()
        self.assertEqual(tb["5210"], Decimal("150000.00"))   # expense
        self.assertEqual(tb["2130"], Decimal("-5000.00"))    # WHT liability
        self.assertEqual(tb["2150"], Decimal("-145000.00"))  # salaries payable

    def test_duplicate_run_rejected(self):
        run_payroll(self.company, date(2026, 6, 30))
        with self.assertRaises(PayrollError):
            run_payroll(self.company, date(2026, 6, 15))  # same month

    def test_pay_salaries_clears_payable(self):
        run = run_payroll(self.company, date(2026, 6, 30))
        pay_salaries(run, date(2026, 7, 1))
        run.refresh_from_db()
        self.assertEqual(run.status, PayrollRun.Status.PAID)
        tb = self._tb()
        self.assertEqual(tb.get("2150", Decimal("0")), Decimal("0.00"))
        self.assertEqual(tb["1120"], Decimal("-145000.00"))
        with self.assertRaises(PayrollError):
            pay_salaries(run, date(2026, 7, 2))

    def test_inactive_employee_excluded(self):
        Employee.objects.create(company=self.company, name="Gone", basic_salary=Decimal("99999"), is_active=False)
        run = run_payroll(self.company, date(2026, 6, 30))
        self.assertEqual(run.payslips.count(), 2)
