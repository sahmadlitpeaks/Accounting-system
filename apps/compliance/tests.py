import json
from unittest import mock

from django.test import TestCase, override_settings

from .adapters import get_adapter
from .http_client import FiscalizationTransportError, is_live


class _FakeInvoice:
    """Minimal duck-typed fiscal document for adapter tests."""

    document_kind = "invoice"

    class _Company:
        name = "Lahore Traders"
        tax_registration_number = "1234567-8"
        country_code = "PK"

    class _Party:
        name = "Acme"
        tax_registration_number = "7654321-0"

    def __init__(self):
        self.company = self._Company()
        self.party = self._Party()
        self.number = "INV-1"
        from datetime import date
        self.date = date(2026, 6, 1)
        self.currency_id = "PKR"
        from decimal import Decimal
        self.net_total = Decimal("100.00")
        self.tax_total = Decimal("18.00")
        self.grand_total = Decimal("118.00")

    class _Lines:
        def select_related(self, *a, **k):
            return []
        def all(self):
            return []

    @property
    def lines(self):
        return self._Lines()


class SandboxVsLiveTests(TestCase):
    def test_sandbox_by_default(self):
        self.assertFalse(is_live("PK"))
        result = get_adapter("PK").submit(_FakeInvoice())
        self.assertTrue(result.success)
        self.assertTrue(result.fbr_invoice_number.startswith("FBR"))

    @override_settings(FISCALIZATION={"PK": {"endpoint": "https://fbr.example/clear", "api_key": "k", "timeout": 5}})
    def test_live_path_parses_provider_response(self):
        self.assertTrue(is_live("PK"))
        fake_response = mock.Mock()
        fake_response.raise_for_status = lambda: None
        fake_response.json = lambda: {"status": "Valid", "invoiceNumber": "FBR999", "qrCode": "QR999"}
        with mock.patch("apps.compliance.http_client.requests.post", return_value=fake_response) as posted:
            result = get_adapter("PK").submit(_FakeInvoice())
        self.assertTrue(posted.called)
        self.assertTrue(result.success)
        self.assertEqual(result.fbr_invoice_number, "FBR999")
        self.assertEqual(result.qr_payload, "QR999")

    @override_settings(FISCALIZATION={"PK": {"endpoint": "https://fbr.example/clear", "api_key": "k", "timeout": 5}})
    def test_live_path_rejection(self):
        fake_response = mock.Mock()
        fake_response.raise_for_status = lambda: None
        fake_response.json = lambda: {"status": "Rejected"}
        with mock.patch("apps.compliance.http_client.requests.post", return_value=fake_response):
            result = get_adapter("PK").submit(_FakeInvoice())
        self.assertFalse(result.success)
        self.assertIn("rejected", result.error.lower())
