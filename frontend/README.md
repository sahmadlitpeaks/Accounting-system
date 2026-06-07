# Finance System — Frontend (Next.js)

A minimal Next.js (App Router, TypeScript) UI for the Django finance API:
token login, a company switcher, financial KPIs (net profit, total assets),
P&L and Balance Sheet, and an invoices list with PDF download. Includes an
**English / Arabic / Urdu** language switcher with automatic **RTL** layout.

## Run

```bash
cd frontend
cp .env.local.example .env.local   # point NEXT_PUBLIC_API_BASE at the Django API
npm install
npm run dev                        # http://localhost:3000
```

The Django API must be running (see the repo root README) and seeded
(`python manage.py seed_demo`). Log in with `admin` / `admin12345`.

## Notes

- Auth uses the DRF token endpoint (`/api/accounts/token/`); the token is kept
  in `localStorage` and sent as `Authorization: Token <…>`.
- The Django side allows the dev origin via `CORS_ALLOWED_ORIGINS`
  (default `http://localhost:3000`).
- RTL: selecting Arabic or Urdu sets `<html dir="rtl">`; layout, tables and
  inputs mirror automatically.
