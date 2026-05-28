"use client";
import Link from "next/link";
import { usePathname } from "next/navigation";
import {
  BarChart2,
  Bot,
  BriefcaseBusiness,
  DollarSign,
  Mail,
  Megaphone,
  MessageSquare,
  Settings,
  Twitter,
  Database,
  Languages,
} from "lucide-react";
import { useI18n } from "@/lib/i18n";

type NavItem = { href: string; labelKey: string; icon: typeof BarChart2 };

const NAV_ITEMS: NavItem[] = [
  { href: "/dashboard", labelKey: "nav.dashboard", icon: BarChart2 },
  { href: "/agents", labelKey: "nav.agents", icon: Bot },
  { href: "/tasks", labelKey: "nav.tasks", icon: BriefcaseBusiness },
  { href: "/social", labelKey: "nav.social", icon: Twitter },
  { href: "/outreach", labelKey: "nav.outreach", icon: Mail },
  { href: "/ads", labelKey: "nav.ads", icon: Megaphone },
  { href: "/finance", labelKey: "nav.finance", icon: DollarSign },
  { href: "/memory", labelKey: "nav.memory", icon: Database },
  { href: "/settings", labelKey: "nav.settings", icon: Settings },
];

export function Sidebar() {
  const pathname = usePathname();
  const { locale, setLocale, t } = useI18n();

  return (
    <aside className="w-56 min-h-screen bg-gray-900 text-white flex flex-col">
      <div className="p-4 border-b border-gray-700">
        <h1 className="text-lg font-bold text-indigo-400">Polsia</h1>
        <p className="text-xs text-gray-400">{t("brand.subtitle")}</p>
      </div>
      <nav className="flex-1 p-3 space-y-1">
        {NAV_ITEMS.map(({ href, labelKey, icon: Icon }) => {
          const active = pathname.startsWith(href);
          return (
            <Link
              key={href}
              href={href}
              className={`flex items-center gap-3 px-3 py-2 rounded-md text-sm transition-colors ${
                active
                  ? "bg-indigo-600 text-white"
                  : "text-gray-300 hover:bg-gray-700"
              }`}
            >
              <Icon size={16} />
              {t(labelKey)}
            </Link>
          );
        })}
      </nav>
      <div className="p-3 border-t border-gray-700">
        <button
          onClick={() => setLocale(locale === "en" ? "zh" : "en")}
          className="flex items-center gap-2 w-full px-3 py-2 rounded-md text-sm text-gray-300 hover:bg-gray-700 transition-colors"
        >
          <Languages size={16} />
          {t("nav.lang")}
        </button>
      </div>
    </aside>
  );
}
