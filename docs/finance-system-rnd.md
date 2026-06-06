# R&D: Multi-Country Finance, Inventory & Order System (UAE / Pakistan)

**Date:** 2026-06-06
**Audience:** Engineering + product stakeholders
**Goal:** Decide *how* to build a finance system usable in the UAE and Pakistan
(and extensible to other countries) covering accounting, inventory, and orders.

---

## 1. Executive summary

We want a finance platform that handles **double-entry accounting, inventory,
and order management** and is legally usable in **two very different tax
regimes**: the UAE and Pakistan.

The single most important finding from this research is that **statutory
real-time e-invoicing is now mandatory in both countries** and the technical
models are completely different:

- **UAE** is moving to a **decentralised "5-corner" Peppol model** using the
  **PINT AE** XML specification, exchanged through an **FTA-Accredited Service
  Provider (ASP)**. Mandatory for large taxpayers (revenue ≥ AED 50m) from
  **1 Jan 2027**, all others from **1 Jul 2027**; voluntary pilot from
  **Jul 2026**.
- **Pakistan** uses a **centralised, real-time clearance model**: every sales
  tax invoice must be pushed to the **FBR computerized system through a
  licensed integrator** and is assigned an FBR invoice number / QR before it is
  valid. Roll-out is already live for large taxpayers, importers and public
  enterprises, expanding to most sectors through 2025–2026.

Because these two compliance models do not look alike, the architecture must
treat **fiscalization/e-invoicing as a pluggable, country-specific adapter**,
not as a feature baked into the invoice screen. Everything else (chart of
accounts, currency, language, tax rules) follows from a standard
**multi-company / multi-currency / localizable** design.

**Recommendation:** Do **not** hand-roll the general ledger. Either (a) extend a
mature open-source ERP — **ERPNext** is the best fit for true open-source +
strong built-in accounting/inventory — with custom UAE/Pakistan localization
apps, or (b) build a focused custom service with a clean modular core if we need
full control of UX and data model. Section 4 gives the decision framework.

---

## 2. Scope & goals

### In scope (functional)
1. **Accounting** — double-entry general ledger, chart of accounts, journals,
   accounts payable (AP), accounts receivable (AR), bank/cash, multi-currency,
   period close, financial statements (P&L, balance sheet, trial balance).
2. **Inventory** — items, units of measure, warehouses/locations, stock moves,
   valuation (FIFO / moving average), batch & serial tracking, reorder levels,
   stock counts.
3. **Orders** — sales orders → delivery → invoice; purchase orders → receipt →
   bill; quotations, returns/credit notes.
4. **Tax & compliance** — VAT (UAE) / Sales Tax + withholding (Pakistan),
   tax-correct invoices, statutory **e-invoicing**, tax returns/reporting data.
5. **Master data** — customers, suppliers, products, price lists, tax codes.
6. **Reporting** — operational + financial + tax/regulatory exports.

### In scope (cross-cutting)
- **Multi-company** (one deployment, several legal entities / countries).
- **Multi-currency** (transaction, company, and reporting currency).
- **Localization** — language (English, **Arabic RTL**, **Urdu RTL**),
  number/date formats, fiscal calendars.
- **Role-based access control**, full **audit trail**, immutability of posted
  entries.

### Out of (initial) scope
Payroll/HR, manufacturing/BOM, fixed-asset depreciation engine, CRM, POS
hardware — all are future modules and the design should not preclude them.

---

## 3. Regulatory & compliance landscape (the differentiator)

This is where a "generic accounting app" fails in production. Summary of the
current rules in each country.

### 3.1 UAE

| Item | Detail |
|------|--------|
| VAT standard rate | **5%** (zero-rated and exempt categories exist) |
| VAT registration threshold | Mandatory at AED 375,000 taxable turnover; voluntary at AED 187,500 |
| Corporate tax | **9%** on taxable profit **above AED 375,000** (0% below); effective since 1 Jun 2023 |
| Currency | **AED** (United Arab Emirates Dirham), pegged to USD |
| Language | English + **Arabic** (Arabic increasingly required on official docs) |
| **E-invoicing model** | **Decentralised 5-corner Peppol**, **PINT AE** structured XML, exchanged via an **FTA-Accredited Service Provider (ASP)**, reported to FTA in near-real time |
| E-invoicing scope | **B2B and B2G** in scope; **B2C currently excluded** |
| E-invoicing timeline | Voluntary pilot **Jul 2026**; mandatory for revenue ≥ **AED 50m** from **1 Jan 2027**; all other businesses **1 Jul 2027** |
| Non-compliance | Penalties (e.g., reported AED 5,000/month for in-scope large taxpayers that fail to issue compliant e-invoices) |

**Design implication:** We must integrate with a **certified ASP** (not talk to
the FTA directly), emit **PINT AE-compliant XML**, and support the Peppol
exchange + response/acknowledgement flow. ASP choice is a procurement decision;
our code targets an **ASP adapter interface**.

### 3.2 Pakistan

| Item | Detail |
|------|--------|
| Sales tax (goods, federal) | **18%** standard GST on goods (sector-specific rates exist) |
| Sales tax on services | **Provincial** (Sindh/Punjab/KPK/Balochistan boards), typically **13–16%** |
| Withholding tax | Extensive WHT regime on payments (income tax) — must be computed and deducted at source |
| Currency | **PKR** (Pakistani Rupee), floating |
| Language | English + **Urdu** |
| **E-invoicing model** | **Centralised real-time clearance**: invoices pushed to the **FBR computerized system via an FBR-licensed integrator**; FBR returns an invoice number / **QR code** that makes the invoice valid |
| Edit/cancel rules | Electronic invoices may only be cancelled/edited **within the FBR system, within a 72-hour window**; later changes need Commissioner approval |
| Timeline | Already mandatory & expanding: large taxpayers, importers, public enterprises live; broad sector expansion (restaurants, transport, couriers, clinics, etc.) through 2025–2026; full digital, manual invoices phased out |
| Non-compliance | Invoices issued outside the FBR system are **invalid** (input-tax impact); monetary penalties from ~PKR 500,000 escalating to ~PKR 3,000,000 |

**Design implication:** Pakistan requires a **synchronous "clearance"** step —
the invoice is **not final until FBR responds**. The order/invoice workflow must
support a "pending fiscalization → cleared (with FBR number + QR) → printable"
state machine, plus the **72-hour amendment** rule.

### 3.3 What this means architecturally

| Concern | UAE | Pakistan |
|---------|-----|----------|
| Model | Decentralised (Peppol) | Centralised (clearance) |
| Format | PINT AE XML | FBR JSON schema |
| Intermediary | Accredited Service Provider | Licensed Integrator |
| Timing | Near-real-time reporting | Real-time clearance before issue |
| Valid invoice gate | Exchange + FTA report | FBR invoice number + QR |

➡️ **One invoice domain model, many fiscalization adapters.** The invoice
lifecycle, numbering, and "is this legally issuable yet?" gate must be
country-driven.

> ⚠️ Tax rates, thresholds and timelines change frequently. Treat the figures
> above as **research snapshots (mid-2026)** and keep rates as **configuration
> data**, never hard-coded. Validate against the official FTA/FBR portals and a
> local tax advisor before go-live. Sources are listed in §15.

---

## 4. Build vs. extend (the key decision)

Building a correct, auditable **double-entry ledger + inventory valuation +
tax engine** from scratch is a multi-year effort. The accounting core is a
**solved problem**; the **localization/compliance** is where the real value and
risk sit. Three viable paths:

### Option A — Extend an open-source ERP (recommended default: ERPNext)
Use a mature core for GL/AP/AR/inventory/orders and build **country
localization apps** (UAE, Pakistan) + **e-invoicing adapters** on top.

- **ERPNext** — truly free/open-source (GPL), strong **built-in accounting +
  inventory + orders** out of the box, multi-currency, app/customization
  framework (Frappe), large community, existing regional localizations to learn
  from. Best when budget matters and we want to own the stack.
- **Odoo** — more polished UX, broader app ecosystem, very mature multi-company
  / multi-currency / tax localization, but the open-source "Community" edition
  is more limited and serious use trends toward paid Enterprise.

✅ Fastest to a compliant MVP; ledger correctness inherited; we focus effort on
UAE/Pakistan specifics.
❌ We live within the framework's data model and conventions; deep custom UX is
harder.

### Option B — Custom build on a modular core
A focused service we fully control (see §6 stack).

✅ Full control of UX, data model, and product direction.
❌ We must implement (and *prove correct*) double-entry posting, inventory
valuation, tax computation, period close, and audit immutability ourselves —
high cost and risk.

### Option C — Hybrid
Use a vetted **double-entry ledger library/service** for the money primitives
and build inventory/orders/compliance around it.

✅ De-risks the hardest correctness problem while keeping product control.
❌ Integration seams; fewer turnkey features than a full ERP.

### Recommendation
- **If the goal is a deployable product fast, with statutory compliance, and
  limited budget → Option A with ERPNext**, plus two localization apps and two
  e-invoicing adapters.
- **If this is a strategic product with strong custom UX needs and a longer
  runway → Option B/C**, but adopt a proven ledger pattern and treat tax +
  fiscalization as first-class plugin layers from day one.

The rest of this document describes the **target architecture in a stack-neutral
way**, so it applies whether we extend ERPNext or build custom.

---

## 5. Proposed architecture (stack-neutral)

```
┌──────────────────────────────────────────────────────────────┐
│                         Clients                              │
│   Web app (React/Next)   ·   Mobile (later)   ·   API users  │
└───────────────┬──────────────────────────────────────────────┘
                │ REST/GraphQL (authn: OAuth2/OIDC, RBAC)
┌───────────────▼──────────────────────────────────────────────┐
│                      Application / API layer                 │
│   Orders · Inventory · Invoicing · Accounting · Reporting    │
└───────────────┬──────────────────────────────────────────────┘
                │  domain services (multi-company aware)
┌───────────────▼──────────────────────────────────────────────┐
│                        Domain core                           │
│  Double-entry Ledger │ Inventory valuation │ Tax engine      │
│  (immutable postings) │  (FIFO/avg)         │ (rule-driven)   │
└───────────────┬───────────────────────────┬──────────────────┘
                │                           │
        ┌───────▼────────┐         ┌────────▼─────────────────┐
        │ Localization   │         │  Fiscalization adapters  │
        │ packs (i18n,   │         │  ┌────────────────────┐  │
        │ CoA, tax rates,│         │  │ UAE: PINT AE / ASP │  │
        │ calendars)     │         │  │      (Peppol)      │  │
        └────────────────┘         │  ├────────────────────┤  │
                                   │  │ PK: FBR integrator │  │
                                   │  │   (real-time clr)  │  │
                                   │  └────────────────────┘  │
                                   └──────────┬───────────────┘
                                              │ outbound (queued, retried)
                                   External: ASP / FBR / banks
```

Key principles:
- **Multi-tenant / multi-company first.** Every transactional row carries a
  `company_id`; ledgers, sequences, and tax settings are per-company.
- **Country pack = data + adapter.** A country is defined by configuration
  (CoA template, tax codes, rates, fiscal calendar, currency, locale) **plus** a
  fiscalization adapter implementing a common interface.
- **Compliance is asynchronous & resilient.** e-Invoice submission is a
  **queued, idempotent, retried** job with a clear status machine, because the
  external system (ASP/FBR) can be slow or down.
- **Posted entries are immutable.** Corrections are new postings
  (reversals/credit notes), never edits — required for audit and for Pakistan's
  72-hour/Commissioner rules.

---

## 6. Suggested technology stack (for a custom build, Option B/C)

| Layer | Choice | Why |
|-------|--------|-----|
| Language/runtime | **TypeScript (Node)** or **Python** | Strong ecosystems, hiring, libraries |
| Backend framework | NestJS (TS) / Django or FastAPI (Py) | Modular, batteries-included, RBAC-friendly |
| Database | **PostgreSQL** | ACID, strong constraints, `numeric` for money, partitioning, RLS for multi-tenant |
| Money type | `NUMERIC(precision,scale)` + integer-minor-units in code | **Never floats** for money |
| Queue/worker | Redis + BullMQ / Celery | Async fiscalization, retries, scheduling |
| Frontend | **React / Next.js** + i18n lib | RTL support for Arabic/Urdu |
| Auth | OAuth2/OIDC (Keycloak/Auth0) + app RBAC | SSO + fine-grained roles |
| Reporting | SQL views + a reporting lib; PDF via headless renderer | Statements, invoices, QR labels |
| Infra | Docker + a managed Postgres; IaC | Reproducible, multi-region option |

(If Option A/ERPNext: stack is **Frappe/ERPNext (Python + MariaDB)**; we add a
custom Frappe app per country plus adapter services.)

---

## 7. Core modules & data model sketch

A minimal but correct relational model (names illustrative):

### 7.1 Accounting
- `company(id, name, country_code, base_currency, fiscal_year_start, tax_ids…)`
- `account(id, company_id, code, name, type[asset/liability/equity/income/expense], parent_id)`
- `journal_entry(id, company_id, date, period_id, source_doc, status[draft/posted/void])`
- `journal_line(id, entry_id, account_id, debit, credit, currency, fx_rate, party_id?)`
  - **Invariant:** `Σ debit = Σ credit` per entry (enforced in domain + DB check).
- `accounting_period(id, company_id, start, end, status[open/closed])`

### 7.2 Master data
- `party(id, company_id, type[customer/supplier], name, tax_reg_no, country, currency, terms)`
- `item(id, company_id, sku, name, uom, type[stock/service], valuation_method, tax_code, hsn_sac?)`
- `warehouse(id, company_id, name, address)`
- `price_list` / `price_list_item`
- `tax_code(id, company_id, name, rate, kind[vat/sales/wht/exempt/zero], accounts…)`

### 7.3 Inventory
- `stock_move(id, company_id, item_id, qty, uom, from_loc, to_loc, date, unit_cost, source_doc)`
- `stock_valuation_layer(id, item_id, qty, value, remaining_qty, method)` — drives
  FIFO/moving-average COGS.
- `batch` / `serial` (optional tracking), `stock_count`/`adjustment`.

### 7.4 Orders → fulfillment → invoice
- `sales_order(id, company_id, party_id, currency, status)` → `so_line`
- `delivery_note(id, so_id, …)` → posts `stock_move`
- `customer_invoice(id, company_id, party_id, currency, status, fiscal_status, fbr_no?, peppol_id?, qr?)` → `invoice_line` + `invoice_tax`
- Mirror for purchasing: `purchase_order` → `goods_receipt` → `supplier_bill`.
- `payment(id, party_id, amount, currency, method, allocations[])`
- `credit_note` / `debit_note` for returns & corrections.

### 7.5 Compliance
- `einvoice_submission(id, invoice_id, country, adapter, payload_ref,
  external_id, status[pending/cleared/reported/failed], response, attempts,
  qr_payload, created_at, cleared_at)`

➡️ The **invoice** carries a generic `fiscal_status`; the **adapter** fills
country-specific fields (FBR number/QR for PK, Peppol transmission/PINT AE
reference for UAE).

---

## 8. Multi-currency design

- Store **transaction currency + amount** *and* the **company base-currency
  amount** with the **FX rate used** on each money line.
- Maintain an `exchange_rate(date, from, to, rate, source)` table; daily refresh.
- Post **realised** FX gain/loss on settlement and **unrealised** on revaluation
  at period close (configurable).
- A separate **reporting/group currency** for consolidated multi-company reports
  (e.g., view AED + PKR entities together).

## 9. Localization design

A **country pack** bundles:
- Chart-of-accounts template + default `tax_code`s and rates.
- Fiscal calendar / year start.
- Locale: language(s), number/date format, **RTL** layout for Arabic & Urdu.
- Invoice print template(s) meeting local statutory fields (e.g., TRN for UAE,
  STRN/NTN + FBR QR for Pakistan).
- A registered **fiscalization adapter**.

Localization is **data + a plugin**, so adding "other countries" later = author a
new pack, not change the core.

## 10. E-invoicing / fiscalization adapter interface

Define one interface, implement per country:

```
interface FiscalizationAdapter {
  // Transform our canonical invoice into the country format
  build(invoice): CountryPayload            // PINT AE XML | FBR JSON

  // Submit: PK = synchronous clearance; UAE = exchange + report
  submit(payload): SubmissionResult         // {externalId, qr?, status, raw}

  // Country amendment/cancel rules (e.g., PK 72h window)
  amend(invoice, reason): SubmissionResult
  cancel(invoice, reason): SubmissionResult

  // Map provider status → our fiscal_status
  poll(externalId): SubmissionStatus
}
```

- **UAE adapter:** build **PINT AE** XML, transmit via the contracted **ASP**
  over Peppol, capture transmission id + FTA reporting acknowledgement.
- **Pakistan adapter:** build **FBR JSON**, call the **licensed integrator** for
  **real-time clearance**, store the returned **FBR invoice number + QR**, and
  enforce the **72-hour** edit/cancel window.
- All submissions go through the **queue** (idempotent by invoice id), with
  retries/backoff and a dead-letter for manual review. The invoice is only
  **legally issuable / printable** once the adapter reports success.

## 11. Security, audit & controls

- **RBAC** by company + role (e.g., AP clerk, AR clerk, accountant, auditor,
  admin); least privilege.
- **Immutable audit log** of who/what/when on every posting and master-data
  change.
- **Segregation of duties** (maker/checker) for posting and payments.
- **Posted-entry immutability**; corrections via reversal/credit note only.
- Encryption in transit + at rest; secrets (ASP/FBR/integrator credentials) in a
  vault; PII handling per local data rules.
- **Backups + point-in-time recovery**; periodic restore drills.

## 12. Phased roadmap

**Phase 0 — Foundation (decision + skeleton)**
- Confirm Build-vs-Extend (Option A/B/C). Pick stack.
- Set up repo, CI, Postgres schema or ERPNext bench, multi-company scaffolding,
  auth/RBAC, money primitives.

**Phase 1 — Accounting core (MVP ledger)**
- CoA, journals, AP/AR, bank/cash, trial balance, P&L, balance sheet,
  multi-currency. *Prove debit=credit invariants with tests.*

**Phase 2 — Inventory + Orders**
- Items, warehouses, stock moves, FIFO/avg valuation; sales & purchase order →
  fulfillment → invoice/bill flows; returns/credit notes.

**Phase 3 — Tax engine + one country (pick UAE *or* PK first)**
- Rule-driven tax computation; statutory invoice template; country pack #1.

**Phase 4 — E-invoicing adapter #1**
- Implement the chosen country's fiscalization (PK clearance *or* UAE
  PINT AE/ASP), queue, retries, status machine. **Pilot.**

**Phase 5 — Second country + adapter #2**
- Add the other country pack + adapter; validate multi-company consolidation
  across AED + PKR.

**Phase 6 — Reporting, hardening, audit**
- Tax-return data exports, financial statements polish, audit log review,
  performance, backups/DR, security review.

A pragmatic **MVP** = Phases 0–4 for **one** country end-to-end (recommend
**Pakistan first** *if* clearance is the more urgent legal gate, or **UAE first**
*if* the customer base is UAE-led), then Phase 5 to add the second.

## 13. Key risks & mitigations

| Risk | Mitigation |
|------|-----------|
| Tax rules/timelines change | Rates & rules as **config/data**; country packs; review with local advisor |
| e-Invoicing provider lock-in | Adapter interface; ASP/integrator behind it |
| Money/rounding bugs | Decimal/minor-units, never floats; golden-file tests |
| Audit/immutability gaps | Append-only postings; maker-checker; full audit log |
| External system downtime (FBR/ASP) | Queue + retries + dead-letter + manual reconcile |
| Underestimating ledger correctness (custom build) | Prefer Option A, or adopt proven ledger pattern + heavy tests |
| RTL/Arabic/Urdu correctness | Build i18n/RTL in from the start, not retrofitted |

## 14. Recommended next steps

1. **Decide Option A vs B/C** (build vs extend ERPNext) — biggest fork.
2. **Pick the first country** to take end-to-end (UAE or Pakistan).
3. **Procure the compliance intermediary** (an FTA **ASP** for UAE / an FBR
   **licensed integrator** for Pakistan) and obtain their API specs early —
   these specs constrain the adapter.
4. Stand up Phase 0 skeleton (repo already initialized on this branch).
5. Validate the tax/compliance assumptions in §3 with a **local tax advisor**.

---

## 15. Sources

Regulatory and product references consulted (mid-2026 snapshots — verify against
official portals before relying on figures):

**UAE e-invoicing & tax**
- ClearTax — e-Invoicing in UAE: https://www.cleartax.com/ae/e-invoicing-uae
- KPMG — UAE technical guidance on mandatory e-invoicing fields: https://kpmg.com/us/en/taxnewsflash/news/2026/02/uae-technical-guidance-mandatory-e-invoicing-fields.html
- Novasoft — UAE e-Invoicing 2026 (FTA mandate, Peppol, penalties): https://novasoft.global/uae-e-invoicing-2026/
- CoralMe — E-Invoicing UAE 2026 mandate guide: https://www.coralme.com/e-invoicing-uae-2026-everything-businesses-need-to-know/
- Wafeq — VAT invoice requirements in UAE: https://www.wafeq.com/en-ae/tax-and-reporting/vat-invoice-requirements-in-uae
- PwC Tax Summaries — UAE corporate income tax: https://taxsummaries.pwc.com/united-arab-emirates/corporate/taxes-on-corporate-income
- UAE Government — Corporate tax (CT): https://u.ae/en/information-and-services/finance-and-investment/taxation/corporate-tax

**Pakistan e-invoicing & tax**
- VATupdate — Pakistan integration & amendment rules for mandatory e-invoicing: https://www.vatupdate.com/2026/04/11/pakistan-clarifies-integration-and-amendment-rules-for-mandatory-e-invoicing/
- Profit (Pakistan Today) — FBR directs integration of e-invoicing with income tax: https://profit.pakistantoday.com.pk/2026/02/19/fbr-directs-integration-of-e-invoicing-with-income-tax-system-for-specified-businesses/
- EDICOM — Pakistan B2B electronic invoicing schedule: https://edicomgroup.com/blog/pakistan-b2b-electronic-invoicing
- vatcalc — Pakistan centralised e-invoicing & fiscal systems: https://www.vatcalc.com/pakistan/pakistan-readies-centralised-e-invoicing-and-fiscal-systems/
- Legal Synergy — FBR Digital Invoicing Integration guide: https://legalsynergy.pk/fbr-digital-invoicing-integration-a-complete-guide-for-businesses-in-pakistan/
- FBR (official): https://www.fbr.gov.pk/
- PwC Tax Summaries — Pakistan withholding taxes: https://taxsummaries.pwc.com/pakistan/corporate/withholding-taxes

**Open-source ERP comparison (build-vs-extend)**
- ERP Research — ERPNext vs Odoo 2026: https://www.erpresearch.com/compare/erpnext-vs-odoo
- ECOSIRE — Top 10 open source ERP systems 2026: https://ecosire.com/blog/open-source-erp-top-10-comparison-2026
- Canduit — ERPNext 16 vs Odoo 19: https://canduit.org/en/blog/erpnext-16-vs-odoo-19-which-erp-powerhouse-is-the-right-investment-for-your-growth-in-2026

> ⚠️ **Disclaimer:** This document is engineering research, not tax or legal
> advice. Confirm all rates, thresholds, deadlines, and technical specifications
> with the official FTA (UAE) / FBR (Pakistan) sources and a qualified local
> tax advisor before implementation or go-live.
