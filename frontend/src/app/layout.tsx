import type { Metadata } from "next";
import "./globals.css";
import { Sidebar } from "@/components/layout/Sidebar";
import { I18nProvider } from "@/lib/i18n";

export const metadata: Metadata = {
  title: "Polsia — AI Business Agent",
  description: "Autonomous AI platform running your company 24/7",
};

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="en" suppressHydrationWarning>
      <body className="bg-gray-950 text-white min-h-screen flex">
        <I18nProvider>
          <Sidebar />
          <main className="flex-1 overflow-auto">{children}</main>
        </I18nProvider>
      </body>
    </html>
  );
}
