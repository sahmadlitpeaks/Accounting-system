"use client";

import { createContext, useContext, useEffect, useState } from "react";
import { Locale, dir, t as translate } from "@/lib/i18n";

interface LocaleCtx {
  locale: Locale;
  setLocale: (l: Locale) => void;
  t: (key: string) => string;
}

const Ctx = createContext<LocaleCtx>({ locale: "en", setLocale: () => {}, t: (k) => k });

export function LocaleProvider({ children }: { children: React.ReactNode }) {
  const [locale, setLocale] = useState<Locale>("en");

  useEffect(() => {
    const saved = (window.localStorage.getItem("locale") as Locale) || "en";
    setLocale(saved);
  }, []);

  useEffect(() => {
    document.documentElement.lang = locale;
    document.documentElement.dir = dir(locale);
    window.localStorage.setItem("locale", locale);
  }, [locale]);

  return (
    <Ctx.Provider value={{ locale, setLocale, t: (k) => translate(locale, k) }}>
      {children}
    </Ctx.Provider>
  );
}

export const useLocale = () => useContext(Ctx);
