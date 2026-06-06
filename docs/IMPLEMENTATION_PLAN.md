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
- [ ] **M8 — Reporting & hardening:** financial statements (P&L, Balance Sheet),
      audit log review, security pass. *(future)*

## Cross-cutting rules

- Money = `Decimal` + `NUMERIC`; **never floats**.
- Posted journal entries are **immutable**; corrections via reversal/credit note.
- Every transactional row carries `company_id` (multi-company).
- e-Invoicing is **async, idempotent, retried** (Celery) — invoice not legally
  issuable until the adapter reports success.
- Tax rates/rules are **data**, not hard-coded.
