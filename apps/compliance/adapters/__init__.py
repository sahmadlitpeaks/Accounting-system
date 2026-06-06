"""Country fiscalization adapters, selected by company country code."""
from .base import FiscalizationAdapter, SubmissionResult
from .pakistan import FBRAdapter
from .uae import UAEPeppolAdapter

_REGISTRY = {
    "AE": UAEPeppolAdapter,
    "PK": FBRAdapter,
}


def get_adapter(country_code: str) -> FiscalizationAdapter:
    cls = _REGISTRY.get(country_code)
    if cls is None:
        raise ValueError(f"No fiscalization adapter registered for {country_code!r}")
    return cls()


__all__ = ["FiscalizationAdapter", "SubmissionResult", "get_adapter"]
