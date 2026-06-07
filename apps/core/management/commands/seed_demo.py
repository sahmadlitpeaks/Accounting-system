"""Seed currencies, two demo companies (UAE + Pakistan) with their Charts of
Accounts, tax codes, and sample master data. Idempotent. Run after migrate:

    python manage.py seed_demo
"""
from datetime import date
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.core.management.base import BaseCommand

from apps.accounting.chart_of_accounts import seed_chart_of_accounts
from apps.accounts.models import Membership, Role
from apps.accounting.models import AccountingPeriod
from apps.accounting.services import get_account
from apps.core.models import Company, Currency
from apps.masterdata.models import Item, Party, TaxCode, UnitOfMeasure, Warehouse


CURRENCIES = [
    ("AED", "UAE Dirham", "د.إ"),
    ("PKR", "Pakistani Rupee", "₨"),
    ("USD", "US Dollar", "$"),
]

COMPANIES = [
    {"name": "Gulf Trading LLC", "country": "AE", "currency": "AED", "trn": "100123456700003",
     "tax": ("UAE VAT 5%", TaxCode.Kind.VAT, Decimal("5"))},
    {"name": "Lahore Traders (Pvt) Ltd", "country": "PK", "currency": "PKR", "trn": "1234567-8",
     "tax": ("PK GST 18%", TaxCode.Kind.SALES, Decimal("18"))},
]


class Command(BaseCommand):
    help = "Seed demo companies (UAE + Pakistan) with CoA, tax codes and master data."

    def handle(self, *args, **options):
        User = get_user_model()
        admin, created = User.objects.get_or_create(
            username="admin", defaults={"is_staff": True, "is_superuser": True, "email": "admin@example.com"},
        )
        if created:
            admin.set_password("admin12345")
            admin.save()
            self.stdout.write("Created superuser 'admin' (password: admin12345)")

        for code, name, symbol in CURRENCIES:
            Currency.objects.get_or_create(code=code, defaults={"name": name, "symbol": symbol})

        for spec in COMPANIES:
            currency = Currency.objects.get(code=spec["currency"])
            company, _ = Company.objects.get_or_create(
                name=spec["name"],
                defaults={"country_code": spec["country"], "base_currency": currency,
                          "tax_registration_number": spec["trn"]},
            )
            created = seed_chart_of_accounts(company)
            self.stdout.write(f"{company}: {created} accounts seeded")

            tax_name, tax_kind, tax_rate = spec["tax"]
            tax_code, _ = TaxCode.objects.get_or_create(
                company=company, name=tax_name,
                defaults={"kind": tax_kind, "rate": tax_rate,
                          "output_account": get_account(company, "2120"),
                          "input_account": get_account(company, "1150")},
            )

            # Pakistan: a supplier withholding-tax code (income tax deducted at source).
            if company.country_code == "PK":
                TaxCode.objects.get_or_create(
                    company=company, name="PK WHT 4%",
                    defaults={"kind": TaxCode.Kind.WITHHOLDING, "rate": Decimal("4")},
                )

            AccountingPeriod.objects.get_or_create(
                company=company, name=f"{date.today():%Y-%m}",
                defaults={"start_date": date.today().replace(day=1), "end_date": date.today()},
            )

            uom, _ = UnitOfMeasure.objects.get_or_create(company=company, code="PCS", defaults={"name": "Pieces"})
            Warehouse.objects.get_or_create(company=company, code="MAIN", defaults={"name": "Main Warehouse"})
            Item.objects.get_or_create(
                company=company, sku="WIDGET-1",
                defaults={"name": "Standard Widget", "uom": uom, "sales_tax_code": tax_code,
                          "standard_cost": Decimal("40"), "sales_price": Decimal("100")},
            )
            Party.objects.get_or_create(
                company=company, name="Acme Customer",
                defaults={"is_customer": True, "currency": currency},
            )
            Party.objects.get_or_create(
                company=company, name="Global Supplier",
                defaults={"is_supplier": True, "currency": currency},
            )

            # Demo users with roles (maker/checker) per company.
            for uname, role in [(f"maker_{company.country_code.lower()}", Role.AP_CLERK),
                                (f"checker_{company.country_code.lower()}", Role.ACCOUNTANT)]:
                user, made = User.objects.get_or_create(username=uname, defaults={"email": f"{uname}@example.com"})
                if made:
                    user.set_password("demo12345")
                    user.save()
                Membership.objects.get_or_create(user=user, company=company, defaults={"role": role})
            Membership.objects.get_or_create(user=admin, company=company, defaults={"role": Role.ADMIN})

        self.stdout.write(self.style.SUCCESS("Demo seed complete."))
