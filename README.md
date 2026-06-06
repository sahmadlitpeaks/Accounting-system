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

## Quick links

| Topic | Where |
|-------|-------|
| Full research study | [`docs/finance-system-rnd.md`](docs/finance-system-rnd.md) |
| Regulatory summary (UAE + Pakistan) | Study §3 |
| Build vs. extend decision | Study §4 |
| Architecture & modules | Study §5–§7 |
| Phased roadmap / MVP | Study §12 |
