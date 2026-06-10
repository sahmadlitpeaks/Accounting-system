# Implementation Plan

Stack (decided): **Django + DRF · PostgreSQL · Celery + Redis · Docker**.
We build module by module, each with models, services, admin, API, and tests.

## Project layout

```
config/            # Django project: settings, urls, celery
apps/
  core/            # Company, Currency, ExchangeRate, base/audit models
  accounting/      # Account (5 types), Period, JournalEntry/Line, posting service, CoA seed
  masterdata/      # Party, Item, UoM, Warehouse, TaxCode, PriceList
  inventory/       # StockMove, StockValuationLayer, valuation (FIFO/avg)
  orders/          # Sales/Purchase orders, Delivery/Receipt, Invoice/Bill, Payment
  tax/             # Tax computation engine
  compliance/      # Fiscalization adapter interface + UAE/PK adapters, EInvoiceSubmission
```

## Modules & order of work

- [x] **M0 — Foundation:** Django project, settings (env-driven), Docker Compose
      (Postgres + Redis + Celery), base abstract models (TimeStamped, audit), health check.
- [x] **M1 — Core:** `Company` (multi-company), `Currency`, `ExchangeRate`.
- [x] **M2 — Accounting:** `Account` (asset/liability/equity/income/expense),
      `AccountingPeriod`, `JournalEntry`, `JournalLine`; **posting service**
      enforcing `Σdebit = Σcredit`; immutability of posted entries; **trial
      balance**. Seed UAE + Pakistan Charts of Accounts.
- [x] **M3 — Master data:** `Party` (customer/supplier), `UnitOfMeasure`,
      `Item`, `Warehouse`, `TaxCode`, `PriceList`.
- [x] **M4 — Inventory:** `StockMove`, `StockValuationLayer`; moving-average /
      FIFO valuation; stock on hand & valuation reports.
- [x] **M5 — Orders:** `SalesOrder`→`Delivery`→`CustomerInvoice`;
      `PurchaseOrder`→`GoodsReceipt`→`SupplierBill`; `Payment`; GL + stock
      postings wired in.
- [x] **M6 — Tax:** rule-driven tax computation (UAE VAT 5%, PK GST 18% +
      withholding); posts to input/output tax accounts.
- [x] **M7 — Compliance:** `FiscalizationAdapter` interface; **UAE** (PINT AE /
      ASP) and **Pakistan** (FBR real-time clearance) adapters (sandbox stubs);
      `EInvoiceSubmission` state machine; Celery submission task.
- [x] **M8 — Reporting:** financial statements (P&L, Balance Sheet) and AR/AP
      aging, derived from the account-type structure.
- [x] **M9 — Corrections & numbering:** customer credit notes (returns/
      corrections, fiscalized), gapless per-company/year document numbering,
      supplier withholding tax.
- [x] **M10 — Close & immutability:** period close/reopen, year-end close into
      retained earnings, posted-entry immutability (reversals only).
- [x] **M11 — Access control & audit:** users/roles (Membership), company-scoped
      data isolation, capability checks, maker-checker on payments, append-only
      audit log.
- [x] **M12 — Frontend & live integrations:**
      - Invoice / credit-note **PDF with statutory QR** (reportlab + qrcode).
      - Fiscalization adapters POST to a **real ASP / FBR endpoint** when
        configured (`settings.FISCALIZATION`), sandbox otherwise.
      - **Next.js** UI (App Router, TypeScript): token login, company switcher,
        KPIs, P&L / Balance Sheet, invoices + PDF, **English/Arabic/Urdu RTL**.
- [x] **M13 — Maturity round:**
      - **FX**: realised gain/loss on settlement (settle at booked rate, plug
        4900/5900) and unrealised revaluation of open foreign-currency AR/AP.
      - **Bank reconciliation** (`banking` app): statement CSV import,
        auto-matching against approved payments, manual matching.
      - **Opening balances**: balanced opening journal entry from CSV +
        opening stock layers (no double-counted GL).
      - **Tax return summary**: output/input/net tax + WHT per period, by code.
      - **Stock valuation report**; **GitHub Actions CI** (backend tests +
        frontend build).
- [ ] **Future:** fixed assets / payroll / manufacturing; UI forms for
      creating orders end-to-end.

## Cross-cutting rules

- Money = `Decimal` + `NUMERIC`; **never floats**.
- Posted journal entries are **immutable**; corrections via reversal/credit note.
- Every transactional row carries `company_id` (multi-company).
- e-Invoicing is **async, idempotent, retried** (Celery) — invoice not legally
  issuable until the adapter reports success.
- Tax rates/rules are **data**, not hard-coded.
