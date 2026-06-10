"""Payroll processing: run a month, then pay it.

  run:  Dr 5210 gross  /  Cr 2130 tax withheld  +  Cr 2150 net payable
  pay:  Dr 2150        /  Cr bank
"""
from decimal import Decimal

from django.db import transaction

from apps.accounting.services import EntryInput, LineInput, get_account, post_entry

from .models import ZERO, Employee, PayrollRun, Payslip


class PayrollError(Exception):
    pass


def _q2(value: Decimal) -> Decimal:
    return Decimal(value).quantize(Decimal("0.01"))


@transaction.atomic
def run_payroll(company, period_date) -> PayrollRun:
    """Create payslips for all active employees for the month of ``period_date``
    and post the salary accrual entry. One run per (company, month)."""
    period = f"{period_date:%Y-%m}"
    if PayrollRun.objects.filter(company=company, period=period).exists():
        raise PayrollError(f"Payroll for {period} has already been run.")
    employees = list(Employee.objects.filter(company=company, is_active=True))
    if not employees:
        raise PayrollError("No active employees to pay.")

    run = PayrollRun.objects.create(company=company, period=period, date=period_date)
    gross_total = ZERO
    tax_total = ZERO
    for emp in employees:
        gross = _q2(emp.gross_salary)
        tax = _q2(gross * emp.tax_rate / Decimal("100"))
        Payslip.objects.create(run=run, employee=emp, gross=gross,
                               tax_deduction=tax, net_pay=_q2(gross - tax))
        gross_total += gross
        tax_total += tax

    net_total = _q2(gross_total - tax_total)
    run.gross_total = _q2(gross_total)
    run.tax_total = _q2(tax_total)
    run.net_total = net_total

    lines = [LineInput(account=get_account(company, "5210"), debit=_q2(gross_total),
                       description=f"Salaries {period}")]
    if tax_total > ZERO:
        lines.append(LineInput(account=get_account(company, "2130"), credit=_q2(tax_total),
                               description="Income tax withheld from salaries"))
    lines.append(LineInput(account=get_account(company, "2150"), credit=net_total,
                           description="Net salaries payable"))
    run.journal_entry = post_entry(EntryInput(
        company=company, date=period_date, memo=f"Payroll {period}",
        source_type="payroll_run", source_id=run.pk, lines=lines,
    ))
    run.save()
    return run


@transaction.atomic
def pay_salaries(run: PayrollRun, on_date, cash_account_code="1120") -> PayrollRun:
    """Settle the net salaries payable for a posted run."""
    if run.status == PayrollRun.Status.PAID:
        raise PayrollError(f"Payroll {run.period} is already paid.")
    run.payment_entry = post_entry(EntryInput(
        company=run.company, date=on_date, memo=f"Pay salaries {run.period}",
        source_type="payroll_payment", source_id=run.pk,
        lines=[
            LineInput(account=get_account(run.company, "2150"), debit=run.net_total),
            LineInput(account=get_account(run.company, cash_account_code), credit=run.net_total),
        ],
    ))
    run.status = PayrollRun.Status.PAID
    run.save(update_fields=["payment_entry", "status", "updated_at"])
    return run
