# Accounting & Finance System (UAE / Pakistan)

A research & design study for building a multi-country finance, inventory and
order-management system that can be deployed in the **UAE**, **Pakistan**, and
extended to other jurisdictions.

> **Status:** R&D / pre-implementation. This repository currently contains the
> research findings and the proposed architecture. See
> [`docs/finance-system-rnd.md`](docs/finance-system-rnd.md) for the full study.

## TL;DR

- **Domain:** Accounting (GL/AP/AR) + Inventory + Sales/Purchase Orders +
  Tax compliance + Invoicing, multi-company and multi-currency.
- **Hard requirement that shapes everything:** statutory **e-invoicing** is now
  mandatory in both target countries (UAE Peppol/PINT AE from 2027; Pakistan
  FBR real-time digital invoicing, already rolling out). The system must be
  built around a pluggable, country-specific **fiscalization/e-invoicing
  adapter** layer.
- **Recommendation:** Localize/extend a mature open-source ERP core
  (**ERPNext**) rather than build the ledger from scratch, OR build a focused
  custom app with a clean modular core. Trade-offs are documented in the study.

## Running the system

```bash
# 1. With Docker (Postgres + Redis + Celery worker + web):
docker compose up --build
docker compose exec web python manage.py seed_demo   # demo companies + CoA + master data

# 2. Locally without infra (SQLite, tasks run inline):
python -m venv .venv && . .venv/bin/activate
pip install -r requirements.txt
python manage.py migrate
python manage.py seed_demo
python manage.py test       # 14 tests: ledger invariants, valuation, order flows
python manage.py runserver  # API at /api/...,  admin at /admin/,  health at /health/
```

Key API roots: `/api/accounting/`, `/api/masterdata/`, `/api/inventory/`,
`/api/orders/`. Trial balance: `/api/accounting/journal-entries/trial-balance/?company=<id>`.

### Modules implemented

| Module | What it does |
|--------|--------------|
| `core` | Multi-company, currencies, FX rates |
| `accounting` | Five account types, periods, **double-entry journal** (`Σdebit = Σcredit` enforced), reversals, trial balance, seeded UAE + PK Charts of Accounts |
| `masterdata` | Parties, items, UoM, warehouses, tax codes, price lists |
| `inventory` | Stock moves, **FIFO + moving-average** valuation |
| `orders` | Sales order→delivery→invoice, purchase order→receipt→bill, payments — all posting to the GL |
| `tax` | Rule-driven VAT / sales tax / withholding computation |
| `compliance` | Fiscalization adapters — **UAE PINT AE/Peppol** & **Pakistan FBR clearance** (sandbox), async via Celery |
| `accounts` | Users, **roles & company-scoped access**, maker-checker on payments, append-only **audit log** |

Reporting: **P&L**, **Balance Sheet** (`/api/accounting/reports/`), **AR/AP aging**
(`/api/orders/reports/`). Period close & year-end close roll into retained
earnings; posted entries are immutable (corrections via reversals / credit notes).
Demo login after `seed_demo`: `admin` / `admin12345`.

See [`docs/IMPLEMENTATION_PLAN.md`](docs/IMPLEMENTATION_PLAN.md) for module status.

## Quick links

| Topic | Where |
|-------|-------|
| Full research study | [`docs/finance-system-rnd.md`](docs/finance-system-rnd.md) |
| Regulatory summary (UAE + Pakistan) | Study §3 |
| Build vs. extend decision | Study §4 |
| Architecture & modules | Study §5–§7 |
| Phased roadmap / MVP | Study §12 |
