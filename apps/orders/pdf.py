"""Tax-invoice / credit-note PDF rendering with a statutory QR code.

The QR encodes the fiscal reference returned by the country adapter (Pakistan
FBR invoice number, or the UAE Peppol transmission id), so a printed invoice
carries its verifiable e-invoicing reference. Works for any fiscal document with
the shared invoice shape (CustomerInvoice, CustomerCreditNote).
"""
import io

import qrcode
from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import getSampleStyleSheet
from reportlab.lib.units import mm
from reportlab.platypus import (
    Image,
    Paragraph,
    SimpleDocTemplate,
    Spacer,
    Table,
    TableStyle,
)


def _qr_image(payload: str, size_mm=28) -> Image | None:
    if not payload:
        return None
    img = qrcode.make(payload)
    buf = io.BytesIO()
    img.save(buf, format="PNG")
    buf.seek(0)
    return Image(buf, width=size_mm * mm, height=size_mm * mm)


def _doc_title(document) -> str:
    return "CREDIT NOTE" if getattr(document, "document_kind", "invoice") == "credit_note" else "TAX INVOICE"


def render_invoice_pdf(document) -> bytes:
    """Render a fiscal document to PDF bytes."""
    company = document.company
    styles = getSampleStyleSheet()
    buf = io.BytesIO()
    doc = SimpleDocTemplate(buf, pagesize=A4, topMargin=18 * mm, bottomMargin=18 * mm)
    elements = []

    # Header: company + document meta + QR.
    fiscal_ref = (
        getattr(document, "fbr_invoice_number", "")
        or getattr(document, "peppol_id", "")
        or document.qr_payload
    )
    header_left = Paragraph(
        f"<b>{company.name}</b><br/>"
        f"TRN/NTN: {company.tax_registration_number or '-'}<br/>"
        f"Country: {company.get_country_code_display()}",
        styles["Normal"],
    )
    meta = Paragraph(
        f"<b>{_doc_title(document)}</b><br/>"
        f"No: {document.number or '-'}<br/>"
        f"Date: {document.date}<br/>"
        f"Currency: {document.currency_id}<br/>"
        f"Fiscal status: {document.fiscal_status}",
        styles["Normal"],
    )
    qr = _qr_image(fiscal_ref)
    top_cells = [[header_left, meta, qr or Paragraph("", styles["Normal"])]]
    top = Table(top_cells, colWidths=[70 * mm, 60 * mm, 35 * mm])
    top.setStyle(TableStyle([("VALIGN", (0, 0), (-1, -1), "TOP")]))
    elements += [top, Spacer(1, 8 * mm)]

    # Bill-to.
    elements.append(Paragraph(
        f"<b>Bill To:</b> {document.party.name}<br/>"
        f"TRN/NTN: {document.party.tax_registration_number or '-'}",
        styles["Normal"],
    ))
    elements.append(Spacer(1, 6 * mm))

    # Line items.
    data = [["#", "Item", "Qty", "Unit Price", "Net", "Tax", "Total"]]
    for i, line in enumerate(document.lines.select_related("item").all(), start=1):
        line_total = line.net_amount + line.tax_amount
        data.append([
            str(i), line.description or line.item.name, f"{line.quantity:g}",
            f"{line.unit_price:.2f}", f"{line.net_amount:.2f}",
            f"{line.tax_amount:.2f}", f"{line_total:.2f}",
        ])
    table = Table(data, colWidths=[10 * mm, 55 * mm, 18 * mm, 24 * mm, 24 * mm, 20 * mm, 24 * mm])
    table.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#1f3b57")),
        ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
        ("FONTSIZE", (0, 0), (-1, -1), 8),
        ("ALIGN", (2, 0), (-1, -1), "RIGHT"),
        ("GRID", (0, 0), (-1, -1), 0.4, colors.grey),
        ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, colors.HexColor("#f2f5f8")]),
    ]))
    elements += [table, Spacer(1, 6 * mm)]

    # Totals.
    totals = [
        ["Net total", f"{document.net_total:.2f} {document.currency_id}"],
        ["Tax total", f"{document.tax_total:.2f} {document.currency_id}"],
        ["Grand total", f"{document.grand_total:.2f} {document.currency_id}"],
    ]
    wht = getattr(document, "withholding_total", None)
    if wht:
        totals.insert(2, ["Withholding tax", f"-{wht:.2f} {document.currency_id}"])
    tt = Table(totals, colWidths=[40 * mm, 50 * mm], hAlign="RIGHT")
    tt.setStyle(TableStyle([
        ("FONTSIZE", (0, 0), (-1, -1), 9),
        ("ALIGN", (1, 0), (1, -1), "RIGHT"),
        ("LINEABOVE", (0, -1), (-1, -1), 0.6, colors.black),
        ("FONTNAME", (0, -1), (-1, -1), "Helvetica-Bold"),
    ]))
    elements.append(tt)

    if fiscal_ref:
        elements += [Spacer(1, 8 * mm), Paragraph(
            f"<font size=7 color='grey'>Fiscal reference: {fiscal_ref}</font>",
            styles["Normal"],
        )]

    doc.build(elements)
    return buf.getvalue()
