"""Starter Charts of Accounts per country.

Code ranges map 1:1 to the five account types (1xxx assets, 2xxx liabilities,
3xxx equity, 4xxx income, 5xxx expenses), which makes the trial balance and
financial statements trivial. Each entry: (code, name, type, is_group, parent_code).

Tax accounts differ by country: UAE surfaces input/output VAT; Pakistan adds
sales-tax payable/receivable plus a withholding-tax-payable account.
"""
from .models import Account, AccountType

A, L, EQ, INC, EXP = (
    AccountType.ASSET,
    AccountType.LIABILITY,
    AccountType.EQUITY,
    AccountType.INCOME,
    AccountType.EXPENSE,
)

# Accounts shared by every company.
_COMMON = [
    ("1000", "Assets", A, True, None),
    ("1100", "Current Assets", A, True, "1000"),
    ("1110", "Cash in Hand", A, False, "1100"),
    ("1120", "Bank Accounts", A, False, "1100"),
    ("1130", "Accounts Receivable", A, False, "1100"),
    ("1140", "Inventory", A, False, "1100"),
    ("1500", "Non-Current Assets", A, True, "1000"),
    ("1510", "Property, Plant & Equipment", A, False, "1500"),
    ("1520", "Accumulated Depreciation", A, False, "1500"),  # contra-asset
    ("2000", "Liabilities", L, True, None),
    ("2100", "Current Liabilities", L, True, "2000"),
    ("2110", "Accounts Payable", L, False, "2100"),
    ("2140", "Goods Received Not Invoiced", L, False, "2100"),
    ("2150", "Salaries Payable", L, False, "2100"),
    ("2500", "Non-Current Liabilities", L, True, "2000"),
    ("2510", "Long-Term Loans", L, False, "2500"),
    ("3000", "Equity / Capital", EQ, True, None),
    ("3100", "Share / Owner's Capital", EQ, False, "3000"),
    ("3200", "Retained Earnings", EQ, False, "3000"),
    ("3300", "Current Year Result", EQ, False, "3000"),
    ("4000", "Income", INC, True, None),
    ("4100", "Sales - Goods", INC, False, "4000"),
    ("4200", "Sales - Services", INC, False, "4000"),
    ("4900", "Other Income / FX Gain", INC, False, "4000"),
    ("5000", "Expenses", EXP, True, None),
    ("5100", "Cost of Goods Sold", EXP, False, "5000"),
    ("5200", "Operating Expenses", EXP, True, "5000"),
    ("5210", "Salaries & Wages", EXP, False, "5200"),
    ("5220", "Rent", EXP, False, "5200"),
    ("5230", "Utilities", EXP, False, "5200"),
    ("5240", "Other Operating Expenses", EXP, False, "5200"),
    ("5300", "Depreciation Expense", EXP, False, "5000"),
    ("5900", "Other Expense / FX Loss", EXP, False, "5000"),
]

# Country-specific tax accounts.
_UAE_TAX = [
    ("1150", "Input VAT Receivable", A, False, "1100"),
    ("2120", "Output VAT Payable", L, False, "2100"),
]

_PK_TAX = [
    ("1150", "Sales Tax Input (Receivable)", A, False, "1100"),
    ("2120", "Sales Tax Output (Payable)", L, False, "2100"),
    ("2130", "Withholding Tax Payable", L, False, "2100"),
]

TEMPLATES = {
    "AE": _COMMON + _UAE_TAX,
    "PK": _COMMON + _PK_TAX,
}


def seed_chart_of_accounts(company) -> int:
    """Create the starter CoA for ``company`` based on its country. Idempotent:
    accounts that already exist (by code) are skipped. Returns count created."""
    template = TEMPLATES.get(company.country_code)
    if template is None:
        raise ValueError(f"No chart-of-accounts template for country {company.country_code!r}")

    existing = set(
        Account.objects.filter(company=company).values_list("code", flat=True)
    )
    by_code = {
        a.code: a for a in Account.objects.filter(company=company)
    }
    created = 0
    # Template is ordered parents-before-children, so a single pass resolves parents.
    for code, name, acc_type, is_group, parent_code in template:
        if code in existing:
            continue
        account = Account.objects.create(
            company=company,
            code=code,
            name=name,
            type=acc_type,
            is_group=is_group,
            parent=by_code.get(parent_code),
        )
        by_code[code] = account
        created += 1
    return created
