import "./globals.css";
import type { Metadata } from "next";
import { LocaleProvider } from "./providers";

export const metadata: Metadata = {
  title: "Finance System — UAE / Pakistan",
  description: "Accounting, inventory and orders",
};

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="en" dir="ltr">
      <body>
        <LocaleProvider>{children}</LocaleProvider>
      </body>
    </html>
  );
}
