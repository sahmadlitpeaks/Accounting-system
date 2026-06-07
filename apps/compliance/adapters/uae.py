"""UAE e-invoicing adapter — PINT AE (Peppol) via an Accredited Service Provider.

The UAE uses a decentralised 5-corner Peppol model: we produce PINT AE-compliant
XML and transmit it through an FTA-accredited ASP, which reports to the FTA in
near-real time. B2C is currently out of scope.

This is a SANDBOX STUB: it builds representative PINT-AE-style XML and simulates
a successful ASP transmission. Swap ``submit`` for a real ASP API client when an
ASP is procured (credentials via settings/secrets).
"""
import uuid
from xml.sax.saxutils import escape

from .base import FiscalizationAdapter, SubmissionResult


class UAEPeppolAdapter(FiscalizationAdapter):
    name = "uae-pint-ae-peppol"
    country = "AE"

    def build(self, invoice) -> str:
        company = invoice.company
        lines_xml = []
        for i, line in enumerate(invoice.lines.select_related("item", "tax_code"), start=1):
            rate = line.tax_code.rate if line.tax_code else 0
            lines_xml.append(
                f"  <InvoiceLine><ID>{i}</ID>"
                f"<Item>{escape(line.item.name)}</Item>"
                f"<Quantity>{line.quantity}</Quantity>"
                f"<LineExtensionAmount currencyID=\"{invoice.currency_id}\">{self._money(line.net_amount)}</LineExtensionAmount>"
                f"<TaxPercent>{rate}</TaxPercent></InvoiceLine>"
            )
        body = "\n".join(lines_xml)
        return (
            "<?xml version=\"1.0\" encoding=\"UTF-8\"?>\n"
            "<Invoice xmlns=\"urn:oasis:names:specification:ubl:schema:xsd:Invoice-2\" "
            "customizationID=\"urn:peppol:pint:billing-1@ae-1\">\n"
            f"  <ID>{escape(invoice.number or str(invoice.pk))}</ID>\n"
            f"  <IssueDate>{invoice.date}</IssueDate>\n"
            f"  <DocumentCurrencyCode>{invoice.currency_id}</DocumentCurrencyCode>\n"
            f"  <AccountingSupplierParty><TRN>{escape(company.tax_registration_number)}</TRN>"
            f"<Name>{escape(company.name)}</Name></AccountingSupplierParty>\n"
            f"  <AccountingCustomerParty><TRN>{escape(invoice.party.tax_registration_number)}</TRN>"
            f"<Name>{escape(invoice.party.name)}</Name></AccountingCustomerParty>\n"
            f"{body}\n"
            f"  <TaxTotal><TaxAmount currencyID=\"{invoice.currency_id}\">{self._money(invoice.tax_total)}</TaxAmount></TaxTotal>\n"
            f"  <LegalMonetaryTotal><PayableAmount currencyID=\"{invoice.currency_id}\">{self._money(invoice.grand_total)}</PayableAmount></LegalMonetaryTotal>\n"
            "</Invoice>"
        )

    def submit(self, invoice) -> SubmissionResult:
        import json

        from ..http_client import is_live, post_json

        payload = self.build(invoice)
        if is_live(self.country):
            # Live: POST PINT AE XML to the accredited service provider (Peppol).
            data = post_json(self.country, payload, content_type="application/xml")
            peppol_id = data.get("transmissionId") or data.get("documentId", "")
            reported = str(data.get("status", "")).lower() in ("reported", "accepted", "success")
            return SubmissionResult(
                success=reported and bool(peppol_id),
                external_id=peppol_id,
                peppol_id=peppol_id,
                qr_payload=peppol_id,
                request_payload=payload,
                response_payload=json.dumps(data),
                error="" if reported else f"ASP rejected: {data.get('status')}",
            )
        # Sandbox: simulate a successful transmission + FTA reporting ack.
        peppol_id = f"PEPPOL-AE-{uuid.uuid4().hex[:16].upper()}"
        return SubmissionResult(
            success=True,
            external_id=peppol_id,
            peppol_id=peppol_id,
            qr_payload=peppol_id,
            request_payload=payload,
            response_payload="{\"status\":\"reported\",\"network\":\"peppol\"}",
        )
