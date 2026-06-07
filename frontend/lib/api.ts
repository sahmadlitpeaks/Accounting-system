// Minimal typed client for the Django REST API using token auth.
const API_BASE = process.env.NEXT_PUBLIC_API_BASE || "http://localhost:8000";

const TOKEN_KEY = "auth_token";

export function getToken(): string | null {
  if (typeof window === "undefined") return null;
  return window.localStorage.getItem(TOKEN_KEY);
}

export function setToken(token: string) {
  window.localStorage.setItem(TOKEN_KEY, token);
}

export function clearToken() {
  window.localStorage.removeItem(TOKEN_KEY);
}

async function request<T>(path: string, options: RequestInit = {}): Promise<T> {
  const headers: Record<string, string> = {
    "Content-Type": "application/json",
    ...(options.headers as Record<string, string>),
  };
  const token = getToken();
  if (token) headers["Authorization"] = `Token ${token}`;

  const res = await fetch(`${API_BASE}${path}`, { ...options, headers });
  if (!res.ok) {
    const body = await res.text();
    throw new Error(`${res.status} ${res.statusText}: ${body}`);
  }
  if (res.status === 204) return undefined as T;
  return res.json() as Promise<T>;
}

export async function login(username: string, password: string): Promise<string> {
  const data = await request<{ token: string }>("/api/accounts/token/", {
    method: "POST",
    body: JSON.stringify({ username, password }),
  });
  setToken(data.token);
  return data.token;
}

export const api = {
  companies: () => request<Paginated<Company>>("/api/accounting/accounts/?page=1").catch(() => ({ results: [] } as any)),
  trialBalance: (company: number) => request<TrialBalanceRow[]>(`/api/accounting/journal-entries/trial-balance/?company=${company}`),
  profitAndLoss: (company: number) => request<ProfitAndLoss>(`/api/accounting/reports/profit-and-loss/?company=${company}`),
  balanceSheet: (company: number) => request<BalanceSheet>(`/api/accounting/reports/balance-sheet/?company=${company}`),
  invoices: (company: number) => request<Paginated<Invoice>>(`/api/orders/customer-invoices/?company=${company}`),
  arAging: (company: number) => request<Aging>(`/api/orders/reports/ar-aging/?company=${company}`),
  invoicePdfUrl: (id: number) => `${API_BASE}/api/orders/customer-invoices/${id}/pdf/`,
};

// --- Types -----------------------------------------------------------------
export interface Paginated<T> { results: T[]; count?: number; }
export interface Company { id: number; name: string; }
export interface TrialBalanceRow { code: string; name: string; type: string; debit: string; credit: string; balance: string; }
export interface StatementRow { code: string; name: string; amount: string; }
export interface ProfitAndLoss { income: StatementRow[]; expenses: StatementRow[]; total_income: string; total_expense: string; net_profit: string; }
export interface BalanceSheet { assets: StatementRow[]; liabilities: StatementRow[]; equity: StatementRow[]; total_assets: string; total_equity_and_liabilities: string; current_year_result: string; balances: boolean; }
export interface Invoice { id: number; number: string; party: number; date: string; grand_total: string; status: string; fiscal_status: string; fbr_invoice_number: string; }
export interface Aging { total: string; buckets: Record<string, string>; }
