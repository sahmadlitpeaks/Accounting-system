"use client";

import { useRouter } from "next/navigation";
import { useState } from "react";
import { login } from "@/lib/api";
import { useLocale } from "./providers";
import { LanguagePicker } from "./components";

export default function LoginPage() {
  const { t } = useLocale();
  const router = useRouter();
  const [username, setUsername] = useState("admin");
  const [password, setPassword] = useState("");
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);

  async function submit(e: React.FormEvent) {
    e.preventDefault();
    setBusy(true);
    setError("");
    try {
      await login(username, password);
      router.push("/dashboard");
    } catch (err: any) {
      setError("Invalid credentials");
    } finally {
      setBusy(false);
    }
  }

  return (
    <div className="login-wrap">
      <form className="card login" onSubmit={submit}>
        <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center" }}>
          <h1 style={{ fontSize: 20, margin: 0 }}>{t("app")}</h1>
          <LanguagePicker />
        </div>
        <p style={{ color: "var(--muted)", fontSize: 13 }}>{t("login")}</p>
        <label>{t("username")}</label>
        <input value={username} onChange={(e) => setUsername(e.target.value)} />
        <label>{t("password")}</label>
        <input type="password" value={password} onChange={(e) => setPassword(e.target.value)} />
        {error && <div className="err">{error}</div>}
        <button className="btn" disabled={busy} type="submit">
          {busy ? "…" : t("login")}
        </button>
      </form>
    </div>
  );
}
