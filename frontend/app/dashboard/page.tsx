"use client";

import { useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import {
  api,
  clearToken,
  getToken,
  BalanceSheet,
  Invoice,
  ProfitAndLoss,
  Paginated,
} from "@/lib/api";
import { useLocale } from "../providers";
import { LanguagePicker, money } from "../components";

export default function Dashboard() {
  const { t } = useLocale();
  const router = useRouter();
  const [company, setCompany] = useState<number>(1);
  const [pnl, setPnl] = useState<ProfitAndLoss | null>(null);
  const [bs, setBs] = useState<BalanceSheet | null>(null);
  const [invoices, setInvoices] = useState<Invoice[]>([]);
  const [error, setError] = useState("");

  useEffect(() => {
    if (!getToken()) router.replace("/");
  }, [router]);

  useEffect(() => {
    let active = true;
    setError("");
    Promise.all([
      api.profitAndLoss(company),
      api.balanceSheet(company),
      api.invoices(company),
    ])
      .then(([p, b, inv]: [ProfitAndLoss, BalanceSheet, Paginated<Invoice>]) => {
        if (!active) return;
        setPnl(p);
        setBs(b);
        setInvoices(inv.results || []);
      })
      .catch((e) => active && setError(String(e.message || e)));
    return () => {
      active = false;
    };
  }, [company]);

  function logout() {
    clearToken();
    router.replace("/");
  }

  return (
    <>
      <div className="topbar">
        <span className="brand">{t("app")}</span>
        <div style={{ display: "flex", gap: 10, alignItems: "center" }}>
          <label>{t("company")}</label>
          <select value={company} onChange={(e) => setCompany(Number(e.target.value))}>
            <option value={1}>Gulf Trading LLC (AE)</option>
            <option value={2}>Lahore Traders (PK)</option>
          </select>
          <LanguagePicker />
          <button onClick={logout}>{t("logout")}</button>
        </div>
      </div>

      <div className="container">
        {error && <div className="card err">{error}</div>}

        <div className="grid">
          <div className="card">
            <h2>{t("netProfit")}</h2>
            <div className="kpi good">{pnl ? money(pnl.net_profit) : "—"}</div>
          </div>
          <div className="card">
            <h2>{t("totalAssets")}</h2>
            <div className="kpi">{bs ? money(bs.total_assets) : "—"}</div>
          </div>
          <div className="card">
            <h2>{t("balanceSheet")}</h2>
            <div className="kpi">{bs ? (bs.balances ? "✓" : "✗") : "—"}</div>
          </div>
        </div>

        {pnl && (
          <div className="card">
            <h2>{t("profitLoss")}</h2>
            <Statement rows={[...pnl.income, ...pnl.expenses]} />
          </div>
        )}

        {bs && (
          <div className="card">
            <h2>{t("balanceSheet")}</h2>
            <Statement rows={[...bs.assets, ...bs.liabilities, ...bs.equity]} />
          </div>
        )}

        <div className="card">
          <h2>{t("invoices")}</h2>
          <table>
            <thead>
              <tr>
                <th>#</th>
                <th>Date</th>
                <th className="num">Total</th>
                <th>Status</th>
                <th>Fiscal</th>
                <th>PDF</th>
              </tr>
            </thead>
            <tbody>
              {invoices.map((inv) => (
                <tr key={inv.id}>
                  <td>{inv.number}</td>
                  <td>{inv.date}</td>
                  <td className="num">{money(inv.grand_total)}</td>
                  <td>{inv.status}</td>
                  <td>
                    <span className={`badge ${inv.fiscal_status === "cleared" ? "cleared" : ""}`}>
                      {inv.fiscal_status}
                    </span>
                  </td>
                  <td>
                    <a href={api.invoicePdfUrl(inv.id)} target="_blank" rel="noreferrer">
                      PDF
                    </a>
                  </td>
                </tr>
              ))}
              {invoices.length === 0 && (
                <tr>
                  <td colSpan={6} style={{ color: "var(--muted)" }}>
                    No invoices yet.
                  </td>
                </tr>
              )}
            </tbody>
          </table>
        </div>
      </div>
    </>
  );
}

function Statement({ rows }: { rows: { code: string; name: string; amount: string }[] }) {
  return (
    <table>
      <thead>
        <tr>
          <th>Code</th>
          <th>Account</th>
          <th className="num">Amount</th>
        </tr>
      </thead>
      <tbody>
        {rows.map((r) => (
          <tr key={r.code}>
            <td>{r.code}</td>
            <td>{r.name}</td>
            <td className="num">{money(r.amount)}</td>
          </tr>
        ))}
      </tbody>
    </table>
  );
}
