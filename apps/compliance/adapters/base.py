"""Common fiscalization adapter contract.

One canonical invoice -> many country adapters. Each adapter ``build``s the
country payload and ``submit``s it (UAE: Peppol exchange + FTA report;
Pakistan: synchronous FBR clearance). The orders module only knows this
interface, never the country specifics.
"""
from dataclasses import dataclass, field
from decimal import Decimal


@dataclass
class SubmissionResult:
    success: bool
    external_id: str = ""
    fbr_invoice_number: str = ""
    peppol_id: str = ""
    qr_payload: str = ""
    request_payload: str = ""
    response_payload: str = ""
    error: str = ""
    extra: dict = field(default_factory=dict)


class FiscalizationAdapter:
    name = "base"
    country = ""

    def build(self, invoice) -> str:
        """Serialize the invoice into the country format (XML/JSON)."""
        raise NotImplementedError

    def submit(self, invoice) -> SubmissionResult:
        """Build + transmit. Must be idempotent w.r.t. the invoice."""
        raise NotImplementedError

    # Helpers shared by adapters.
    @staticmethod
    def _money(value: Decimal) -> str:
        return f"{Decimal(value):.2f}"
