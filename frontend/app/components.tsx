"use client";

import { Locale } from "@/lib/i18n";
import { useLocale } from "./providers";

export function LanguagePicker() {
  const { locale, setLocale, t } = useLocale();
  return (
    <select
      aria-label={t("language")}
      value={locale}
      onChange={(e) => setLocale(e.target.value as Locale)}
    >
      <option value="en">English</option>
      <option value="ar">العربية</option>
      <option value="ur">اردو</option>
    </select>
  );
}

export function money(value: string | number) {
  const n = typeof value === "string" ? parseFloat(value) : value;
  return n.toLocaleString(undefined, { minimumFractionDigits: 2, maximumFractionDigits: 2 });
}
