"""Fixed-asset lifecycle: acquire -> depreciate monthly -> dispose."""
from decimal import Decimal

from django.db import transaction

from apps.accounting.services import EntryInput, LineInput, get_account, post_entry

from .models import ZERO, DepreciationEntry, FixedAsset


class AssetError(Exception):
    pass


def _q2(value: Decimal) -> Decimal:
    return Decimal(value).quantize(Decimal("0.01"))


@transaction.atomic
def acquire_asset(*, company, category, name, acquisition_date, cost,
                  salvage_value=ZERO, useful_life_months=None,
                  credit_account_code="1120") -> FixedAsset:
    """Capitalise a new asset: Dr asset account / Cr bank (or AP via 2110)."""
    cost = _q2(cost)
    asset = FixedAsset.objects.create(
        company=company, category=category, name=name,
        acquisition_date=acquisition_date, cost=cost,
        salvage_value=_q2(salvage_value),
        useful_life_months=useful_life_months or category.useful_life_months,
    )
    entry = post_entry(EntryInput(
        company=company, date=acquisition_date,
        memo=f"Acquire asset {name}",
        source_type="fixed_asset", source_id=asset.pk,
        lines=[
            LineInput(account=get_account(company, category.asset_account_code), debit=cost),
            LineInput(account=get_account(company, credit_account_code), credit=cost),
        ],
    ))
    asset.acquisition_entry = entry
    asset.save(update_fields=["acquisition_entry"])
    return asset


@transaction.atomic
def run_depreciation(company, period_date) -> list:
    """Post straight-line depreciation for every active asset for the month of
    ``period_date``. Idempotent: assets already depreciated for the period (or
    fully depreciated) are skipped. Returns the DepreciationEntry rows created."""
    period = f"{period_date:%Y-%m}"
    created = []
    assets = FixedAsset.objects.select_for_update().filter(
        company=company, status=FixedAsset.Status.ACTIVE,
        acquisition_date__lte=period_date,
    )
    for asset in assets:
        if DepreciationEntry.objects.filter(asset=asset, period=period).exists():
            continue
        amount = min(asset.monthly_depreciation, asset.remaining_depreciable)
        if amount <= ZERO:
            continue
        entry = post_entry(EntryInput(
            company=company, date=period_date,
            memo=f"Depreciation {period} {asset.name}",
            source_type="depreciation", source_id=asset.pk,
            lines=[
                LineInput(account=get_account(company, asset.category.expense_account_code), debit=amount),
                LineInput(account=get_account(company, asset.category.accum_depreciation_code), credit=amount),
            ],
        ))
        asset.accumulated_depreciation = _q2(asset.accumulated_depreciation + amount)
        asset.save(update_fields=["accumulated_depreciation", "updated_at"])
        created.append(DepreciationEntry.objects.create(
            asset=asset, period=period, amount=amount, journal_entry=entry,
        ))
    return created


@transaction.atomic
def dispose_asset(asset: FixedAsset, on_date, proceeds=ZERO, cash_account_code="1120"):
    """Remove the asset from the books. Proceeds vs book value posts a disposal
    gain (4900) or loss (5900)."""
    asset.refresh_from_db()  # never compute disposal from a stale instance
    if asset.status == FixedAsset.Status.DISPOSED:
        raise AssetError(f"Asset {asset.name} is already disposed.")
    proceeds = _q2(proceeds)
    company = asset.company
    lines = []
    if proceeds > ZERO:
        lines.append(LineInput(account=get_account(company, cash_account_code), debit=proceeds))
    if asset.accumulated_depreciation > ZERO:
        lines.append(LineInput(
            account=get_account(company, asset.category.accum_depreciation_code),
            debit=asset.accumulated_depreciation,
        ))
    lines.append(LineInput(
        account=get_account(company, asset.category.asset_account_code), credit=asset.cost,
    ))
    result = proceeds - asset.book_value  # positive = gain
    if result > ZERO:
        lines.append(LineInput(account=get_account(company, "4900"), credit=result,
                               description=f"Gain on disposal of {asset.name}"))
    elif result < ZERO:
        lines.append(LineInput(account=get_account(company, "5900"), debit=-result,
                               description=f"Loss on disposal of {asset.name}"))
    entry = post_entry(EntryInput(
        company=company, date=on_date,
        memo=f"Dispose asset {asset.name}",
        source_type="fixed_asset_disposal", source_id=asset.pk, lines=lines,
    ))
    asset.status = FixedAsset.Status.DISPOSED
    asset.save(update_fields=["status", "updated_at"])
    return entry
