"""Pakistan e-invoicing adapter — FBR real-time clearance via a licensed integrator.

Pakistan uses a centralised model: each sales-tax invoice is pushed in real time
to the FBR system through a licensed integrator, which returns an FBR invoice
number + QR that make the invoice valid. Edits/cancellations are only allowed
within FBR within a 72-hour window.

This is a SANDBOX STUB: it builds the FBR-style JSON and simulates a successful
clearance. Swap ``submit`` for a real licensed-integrator API client (credentials
via settings/secrets) when one is procured.
"""
import json
import uuid

from .base import FiscalizationAdapter, SubmissionResult


class FBRAdapter(FiscalizationAdapter):
    name = "pakistan-fbr-clearance"
    country = "PK"

    def build(self, invoice) -> str:
        company = invoice.company
        items = []
        for line in invoice.lines.select_related("item", "tax_code"):
            items.append({
                "hsCode": line.item.hsn_sac_code or "0000.0000",
                "productDescription": line.item.name,
                "quantity": str(line.quantity),
                "valueSalesExcludingST": self._money(line.net_amount),
                "salesTaxApplicable": self._money(line.tax_amount),
                "rate": f"{(line.tax_code.rate if line.tax_code else 0)}%",
            })
        kind = getattr(invoice, "document_kind", "invoice")
        doc = {
            "invoiceType": "Credit Note" if kind == "credit_note" else "Sale Invoice",
            "invoiceDate": str(invoice.date),
            "sellerNTNCNIC": company.tax_registration_number,
            "sellerBusinessName": company.name,
            "buyerNTNCNIC": invoice.party.tax_registration_number,
            "buyerBusinessName": invoice.party.name,
            "totalValueExcludingST": self._money(invoice.net_total),
            "totalSalesTax": self._money(invoice.tax_total),
            "totalValueIncludingST": self._money(invoice.grand_total),
            "items": items,
        }
        return json.dumps(doc, ensure_ascii=False)

    def submit(self, invoice) -> SubmissionResult:
        from ..http_client import is_live, post_json

        payload = self.build(invoice)
        if is_live(self.country):
            # Live: POST to the FBR licensed integrator for real-time clearance.
            data = post_json(self.country, payload)
            fbr_number = data.get("invoiceNumber") or data.get("fbrInvoiceNumber", "")
            valid = str(data.get("status", "")).lower() in ("valid", "cleared", "success")
            return SubmissionResult(
                success=valid and bool(fbr_number),
                external_id=fbr_number,
                fbr_invoice_number=fbr_number,
                qr_payload=data.get("qrCode") or fbr_number,
                request_payload=payload,
                response_payload=json.dumps(data),
                error="" if valid else f"FBR rejected: {data.get('status')}",
            )
        # Sandbox: simulate a successful real-time clearance.
        fbr_number = f"FBR{uuid.uuid4().int % (10 ** 12):012d}"
        return SubmissionResult(
            success=True,
            external_id=fbr_number,
            fbr_invoice_number=fbr_number,
            qr_payload=fbr_number,  # FBR returns a QR encoding this reference
            request_payload=payload,
            response_payload=json.dumps({"status": "Valid", "invoiceNumber": fbr_number}),
        )
