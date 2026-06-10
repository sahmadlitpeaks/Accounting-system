"use client";

import Link from "next/link";
import { useRouter } from "next/navigation";
import { useCallback, useEffect, useState } from "react";
import {
  api,
  getToken,
  ItemRef,
  PartyRef,
  SalesOrder,
  TaxCodeRef,
  WarehouseRef,
} from "@/lib/api";
import { LanguagePicker } from "../components";
import { useLocale } from "../providers";

const COMPANY_CURRENCY: Record<number, string> = { 1: "AED", 2: "PKR" };

export default function OrdersPage() {
  const { t } = useLocale();
  const router = useRouter();
  const [company, setCompany] = useState<number>(1);
  const [orders, setOrders] = useState<SalesOrder[]>([]);
  const [customers, setCustomers] = useState<PartyRef[]>([]);
  const [items, setItems] = useState<ItemRef[]>([]);
  const [taxCodes, setTaxCodes] = useState<TaxCodeRef[]>([]);
  const [warehouses, setWarehouses] = useState<WarehouseRef[]>([]);
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);

  // Form state.
  const [party, setParty] = useState<number>(0);
  const [itemId, setItemId] = useState<number>(0);
  const [quantity, setQuantity] = useState("1");
  const [unitPrice, setUnitPrice] = useState("0");
  const [taxCode, setTaxCode] = useState<number>(0);

  useEffect(() => {
    if (!getToken()) router.replace("/");
  }, [router]);

  const reload = useCallback(() => {
    setError("");
    Promise.all([
      api.salesOrders(company),
      api.parties(company),
      api.items(company),
      api.taxCodes(company),
      api.warehouses(company),
    ])
      .then(([so, p, it, tc, wh]) => {
        setOrders(so.results || []);
        setCustomers(p.results || []);
        setItems(it.results || []);
        setTaxCodes(tc.results || []);
        setWarehouses(wh.results || []);
      })
      .catch((e) => setError(String(e.message || e)));
  }, [company]);

  useEffect(reload, [reload]);

  // Picking an item pre-fills its list price and default tax code.
  function pickItem(id: number) {
    setItemId(id);
    const item = items.find((i) => i.id === id);
    if (item) {
      setUnitPrice(item.sales_price || "0");
      if (item.sales_tax_code) setTaxCode(item.sales_tax_code);
    }
  }

  async function createOrder(e: React.FormEvent) {
    e.preventDefault();
    if (!party || !itemId || !warehouses.length) return;
    setBusy(true);
    setError("");
    try {
      await api.createSalesOrder({
        company,
        party,
        date: new Date().toISOString().slice(0, 10),
        currency: COMPANY_CURRENCY[company] || "AED",
        warehouse: warehouses[0].id,
        lines: [{ item: itemId, quantity, unit_price: unitPrice, tax_code: taxCode || null }],
      });
      reload();
    } catch (err: any) {
      setError(String(err.message || err));
    } finally {
      setBusy(false);
    }
  }

  async function act(fn: () => Promise<unknown>) {
    setBusy(true);
    setError("");
    try {
      await fn();
      reload();
    } catch (err: any) {
      setError(String(err.message || err));
    } finally {
      setBusy(false);
    }
  }

  return (
    <>
      <div className="topbar">
        <span className="brand">
          <Link href="/dashboard" style={{ color: "#fff" }}>{t("app")}</Link> · {t("orders")}
        </span>
        <div style={{ display: "flex", gap: 10, alignItems: "center" }}>
          <label>{t("company")}</label>
          <select value={company} onChange={(e) => setCompany(Number(e.target.value))}>
            <option value={1}>Gulf Trading LLC (AE)</option>
            <option value={2}>Lahore Traders (PK)</option>
          </select>
          <LanguagePicker />
        </div>
      </div>

      <div className="container">
        {error && <div className="card err">{error}</div>}

        <form className="card" onSubmit={createOrder}>
          <h2>{t("newOrder")}</h2>
          <div className="grid">
            <div>
              <label>{t("customer")}</label>
              <select value={party} onChange={(e) => setParty(Number(e.target.value))} required>
                <option value={0}>—</option>
                {customers.map((c) => <option key={c.id} value={c.id}>{c.name}</option>)}
              </select>
            </div>
            <div>
              <label>{t("item")}</label>
              <select value={itemId} onChange={(e) => pickItem(Number(e.target.value))} required>
                <option value={0}>—</option>
                {items.map((i) => <option key={i.id} value={i.id}>{i.sku} {i.name}</option>)}
              </select>
            </div>
            <div>
              <label>{t("quantity")}</label>
              <input type="number" min="0.0001" step="any" value={quantity}
                     onChange={(e) => setQuantity(e.target.value)} required />
            </div>
            <div>
              <label>{t("unitPrice")}</label>
              <input type="number" min="0" step="0.01" value={unitPrice}
                     onChange={(e) => setUnitPrice(e.target.value)} required />
            </div>
            <div>
              <label>Tax</label>
              <select value={taxCode} onChange={(e) => setTaxCode(Number(e.target.value))}>
                <option value={0}>—</option>
                {taxCodes.map((tc) => <option key={tc.id} value={tc.id}>{tc.name}</option>)}
              </select>
            </div>
          </div>
          <button className="btn" style={{ width: "auto", marginTop: 12 }} disabled={busy} type="submit">
            {t("create")}
          </button>
        </form>

        <div className="card">
          <h2>{t("orders")}</h2>
          <table>
            <thead>
              <tr>
                <th>#</th>
                <th>{t("customer")}</th>
                <th>Date</th>
                <th>{t("status")}</th>
                <th>{t("actions")}</th>
              </tr>
            </thead>
            <tbody>
              {orders.map((o) => (
                <tr key={o.id}>
                  <td>SO-{o.id}</td>
                  <td>{customers.find((c) => c.id === o.party)?.name || o.party}</td>
                  <td>{o.date}</td>
                  <td><span className="badge">{o.status}</span></td>
                  <td style={{ display: "flex", gap: 8 }}>
                    {(o.status === "draft" || o.status === "confirmed") && (
                      <button disabled={busy} onClick={() => act(() => api.deliverOrder(o.id))}>
                        {t("deliver")}
                      </button>
                    )}
                    {o.status === "delivered" && (
                      <button disabled={busy} onClick={() => act(() => api.invoiceOrder(o.id))}>
                        {t("invoiceAction")}
                      </button>
                    )}
                  </td>
                </tr>
              ))}
              {orders.length === 0 && (
                <tr><td colSpan={5} style={{ color: "var(--muted)" }}>No orders yet.</td></tr>
              )}
            </tbody>
          </table>
        </div>
      </div>
    </>
  );
}
