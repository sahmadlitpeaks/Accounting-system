from datetime import date
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.test import TestCase

from apps.accounting.chart_of_accounts import seed_chart_of_accounts
from apps.core.models import Company, Currency
from apps.masterdata.models import Party
from apps.orders.models import Payment
from apps.orders.services import approve_payment, create_payment_request

from .access import PermissionDenied, can, require, user_company_ids
from .audit import _user  # noqa: F401 (ensure module import side effects)
from .middleware import set_current_user
from .models import AuditLog, Membership, Role

User = get_user_model()


def _company(name="Co", code="AED"):
    cur = Currency.objects.create(code=code, name=code)
    company = Company.objects.create(name=name, country_code="AE", base_currency=cur)
    seed_chart_of_accounts(company)
    return company, cur


class RBACTests(TestCase):
    def setUp(self):
        self.company, _ = _company()
        self.admin = User.objects.create_user("admin")
        self.clerk = User.objects.create_user("clerk")
        self.outsider = User.objects.create_user("outsider")
        Membership.objects.create(user=self.admin, company=self.company, role=Role.ADMIN)
        Membership.objects.create(user=self.clerk, company=self.company, role=Role.AP_CLERK)

    def test_company_isolation(self):
        self.assertIn(self.company.id, user_company_ids(self.admin))
        self.assertEqual(user_company_ids(self.outsider), [])

    def test_capabilities_by_role(self):
        self.assertTrue(can(self.admin, self.company, "approve_payment"))
        self.assertFalse(can(self.clerk, self.company, "approve_payment"))  # clerk cannot approve
        self.assertTrue(can(self.clerk, self.company, "create_payment"))    # but can create
        self.assertFalse(can(self.outsider, self.company, "view"))

    def test_require_raises(self):
        with self.assertRaises(PermissionDenied):
            require(self.clerk, self.company, "approve_payment")


class MakerCheckerTests(TestCase):
    def setUp(self):
        self.company, self.cur = _company()
        self.maker = User.objects.create_user("maker")
        self.checker = User.objects.create_user("checker")
        Membership.objects.create(user=self.maker, company=self.company, role=Role.AP_CLERK)
        Membership.objects.create(user=self.checker, company=self.company, role=Role.ACCOUNTANT)
        self.supplier = Party.objects.create(company=self.company, name="Supp", is_supplier=True, currency=self.cur)

    def _draft(self):
        return create_payment_request(
            company=self.company, party=self.supplier, direction=Payment.Direction.OUTBOUND,
            date=date.today(), currency=self.cur, amount=Decimal("100"), created_by=self.maker,
        )

    def test_draft_is_not_posted(self):
        pay = self._draft()
        self.assertEqual(pay.approval_status, Payment.Approval.DRAFT)
        self.assertIsNone(pay.journal_entry)

    def test_maker_cannot_approve_own_payment(self):
        pay = self._draft()
        with self.assertRaises(PermissionDenied):
            approve_payment(pay, self.maker)  # same user

    def test_checker_approves_and_posts(self):
        pay = self._draft()
        approve_payment(pay, self.checker)
        pay.refresh_from_db()
        self.assertEqual(pay.approval_status, Payment.Approval.APPROVED)
        self.assertEqual(pay.approved_by, self.checker)
        self.assertIsNotNone(pay.journal_entry)  # now posted to the GL


class AuditLogTests(TestCase):
    def setUp(self):
        self.company, self.cur = _company()
        self.user = User.objects.create_user("u1")

    def test_changes_are_logged_with_user(self):
        set_current_user(self.user)
        try:
            party = Party.objects.create(company=self.company, name="Acme", is_customer=True)
            party.name = "Acme Renamed"
            party.save()
        finally:
            set_current_user(None)

        logs = AuditLog.objects.filter(model="Party", object_id=str(party.pk)).order_by("timestamp")
        actions = [l.action for l in logs]
        self.assertEqual(actions, ["create", "update"])
        self.assertEqual(logs[0].user, self.user)
        self.assertIn("name", logs[1].changes)
        self.assertEqual(logs[1].changes["name"], ["Acme", "Acme Renamed"])
