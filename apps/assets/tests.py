from datetime import date
from decimal import Decimal

from django.test import TestCase

from apps.accounting.chart_of_accounts import seed_chart_of_accounts
from apps.accounting.services import trial_balance
from apps.core.models import Company, Currency

from .models import FixedAsset
from .services import AssetError, acquire_asset, dispose_asset, run_depreciation


class FixedAssetTests(TestCase):
    def setUp(self):
        cur = Currency.objects.create(code="AED", name="Dirham")
        self.company = Company.objects.create(name="Gulf", country_code="AE", base_currency=cur)
        seed_chart_of_accounts(self.company)
        from .models import AssetCategory
        self.cat = AssetCategory.objects.create(company=self.company, name="Vehicles", useful_life_months=48)

    def _tb(self):
        return {r["code"]: r["balance"] for r in trial_balance(self.company)}

    def _asset(self, cost="48000", salvage="0", life=None):
        return acquire_asset(company=self.company, category=self.cat, name="Delivery van",
                             acquisition_date=date(2026, 1, 15), cost=Decimal(cost),
                             salvage_value=Decimal(salvage), useful_life_months=life)

    def test_acquisition_capitalises(self):
        self._asset()
        tb = self._tb()
        self.assertEqual(tb["1510"], Decimal("48000.00"))
        self.assertEqual(tb["1120"], Decimal("-48000.00"))

    def test_monthly_depreciation_and_idempotency(self):
        asset = self._asset()  # 48000 over 48 months -> 1000/month
        run_depreciation(self.company, date(2026, 1, 31))
        run_depreciation(self.company, date(2026, 1, 31))  # second run: no-op
        asset.refresh_from_db()
        self.assertEqual(asset.accumulated_depreciation, Decimal("1000.00"))
        tb = self._tb()
        self.assertEqual(tb["5300"], Decimal("1000.00"))
        self.assertEqual(tb["1520"], Decimal("-1000.00"))  # contra-asset credit
        # Next month adds another 1000.
        run_depreciation(self.company, date(2026, 2, 28))
        asset.refresh_from_db()
        self.assertEqual(asset.accumulated_depreciation, Decimal("2000.00"))

    def test_salvage_value_respected(self):
        asset = self._asset(cost="1200", salvage="200", life=10)  # base 1000 -> 100/month
        run_depreciation(self.company, date(2026, 1, 31))
        asset.refresh_from_db()
        self.assertEqual(asset.monthly_depreciation, Decimal("100.00"))
        self.assertEqual(asset.accumulated_depreciation, Decimal("100.00"))

    def test_disposal_with_gain(self):
        asset = self._asset()
        run_depreciation(self.company, date(2026, 1, 31))  # book value 47000
        dispose_asset(asset, date(2026, 2, 1), proceeds=Decimal("47500"))
        asset.refresh_from_db()
        self.assertEqual(asset.status, FixedAsset.Status.DISPOSED)
        tb = self._tb()
        self.assertEqual(tb.get("1510", Decimal("0")), Decimal("0.00"))  # cost cleared
        self.assertEqual(tb.get("1520", Decimal("0")), Decimal("0.00"))  # accum cleared
        self.assertEqual(tb["4900"], Decimal("-500.00"))  # 47500 - 47000 gain
        with self.assertRaises(AssetError):
            dispose_asset(asset, date(2026, 2, 2))

    def test_disposal_with_loss(self):
        asset = self._asset()
        dispose_asset(asset, date(2026, 2, 1), proceeds=Decimal("40000"))
        tb = self._tb()
        self.assertEqual(tb["5900"], Decimal("8000.00"))  # 48000 book - 40000 proceeds
