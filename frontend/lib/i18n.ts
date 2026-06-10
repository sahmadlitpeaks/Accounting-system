// Lightweight localization with RTL support for Arabic (UAE) and Urdu (Pakistan).
export type Locale = "en" | "ar" | "ur";

export const RTL_LOCALES: Locale[] = ["ar", "ur"];

export function dir(locale: Locale): "rtl" | "ltr" {
  return RTL_LOCALES.includes(locale) ? "rtl" : "ltr";
}

type Dict = Record<string, string>;

const STRINGS: Record<Locale, Dict> = {
  en: {
    app: "Finance System",
    login: "Sign in",
    username: "Username",
    password: "Password",
    dashboard: "Dashboard",
    company: "Company",
    trialBalance: "Trial Balance",
    profitLoss: "Profit & Loss",
    balanceSheet: "Balance Sheet",
    invoices: "Invoices",
    netProfit: "Net Profit",
    totalAssets: "Total Assets",
    arAging: "Receivables Aging",
    logout: "Sign out",
    language: "Language",
    orders: "Sales Orders",
    newOrder: "New Order",
    customer: "Customer",
    item: "Item",
    quantity: "Quantity",
    unitPrice: "Unit Price",
    create: "Create",
    deliver: "Deliver",
    invoiceAction: "Invoice",
    status: "Status",
    actions: "Actions",
  },
  ar: {
    app: "النظام المالي",
    login: "تسجيل الدخول",
    username: "اسم المستخدم",
    password: "كلمة المرور",
    dashboard: "لوحة التحكم",
    company: "الشركة",
    trialBalance: "ميزان المراجعة",
    profitLoss: "الأرباح والخسائر",
    balanceSheet: "الميزانية العمومية",
    invoices: "الفواتير",
    netProfit: "صافي الربح",
    totalAssets: "إجمالي الأصول",
    arAging: "أعمار الذمم المدينة",
    logout: "تسجيل الخروج",
    language: "اللغة",
    orders: "أوامر البيع",
    newOrder: "أمر جديد",
    customer: "العميل",
    item: "الصنف",
    quantity: "الكمية",
    unitPrice: "سعر الوحدة",
    create: "إنشاء",
    deliver: "تسليم",
    invoiceAction: "فوترة",
    status: "الحالة",
    actions: "إجراءات",
  },
  ur: {
    app: "مالیاتی نظام",
    login: "سائن ان",
    username: "صارف نام",
    password: "پاس ورڈ",
    dashboard: "ڈیش بورڈ",
    company: "کمپنی",
    trialBalance: "ٹرائل بیلنس",
    profitLoss: "نفع و نقصان",
    balanceSheet: "بیلنس شیٹ",
    invoices: "انوائسز",
    netProfit: "خالص منافع",
    totalAssets: "کل اثاثے",
    arAging: "وصولیوں کی عمر",
    logout: "سائن آؤٹ",
    language: "زبان",
    orders: "سیلز آرڈرز",
    newOrder: "نیا آرڈر",
    customer: "گاہک",
    item: "آئٹم",
    quantity: "مقدار",
    unitPrice: "فی یونٹ قیمت",
    create: "بنائیں",
    deliver: "ڈیلیور",
    invoiceAction: "انوائس",
    status: "حالت",
    actions: "ایکشنز",
  },
};

export function t(locale: Locale, key: string): string {
  return STRINGS[locale]?.[key] ?? STRINGS.en[key] ?? key;
}
