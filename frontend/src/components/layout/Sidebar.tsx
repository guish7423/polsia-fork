"use client";
import Link from "next/link";
import { usePathname } from "next/navigation";
import {
  BarChart2,
  BookOpen,
  Bot,
  BriefcaseBusiness,
  CalendarClock,
  Container,
  Database,
  DollarSign,
  Gauge,
  Languages,
  Mail,
  Megaphone,
  MessageSquare,
  Plug,
  Puzzle,
  ScrollText,
  Search,
  Settings,
  Store,
  Twitter,
} from "lucide-react";
import { useI18n } from "@/lib/i18n";
import { GlobalSearch } from "./GlobalSearch";
import { NotificationBell } from "./NotificationBell";

type NavItem = { href: string; labelKey: string; icon: typeof BarChart2 };

type NavGroup = { labelKey: string; items: NavItem[] };

const NAV_GROUPS: NavGroup[] = [
  {
    labelKey: "nav.group.operations",
    items: [
      { href: "/dashboard", labelKey: "nav.dashboard", icon: BarChart2 },
      { href: "/agents", labelKey: "nav.agents", icon: Bot },
      { href: "/tasks", labelKey: "nav.tasks", icon: BriefcaseBusiness },
      { href: "/social", labelKey: "nav.social", icon: Twitter },
      { href: "/outreach", labelKey: "nav.outreach", icon: Mail },
      { href: "/ads", labelKey: "nav.ads", icon: Megaphone },
      { href: "/finance", labelKey: "nav.finance", icon: DollarSign },
      { href: "/memory", labelKey: "nav.memory", icon: Database },
    ],
  },
  {
    labelKey: "nav.group.system",
    items: [
      { href: "/quota", labelKey: "nav.quota", icon: Gauge },
      { href: "/knowledge", labelKey: "nav.knowledge", icon: BookOpen },
      { href: "/mcp", labelKey: "nav.mcp", icon: Plug },
      { href: "/plugins", labelKey: "nav.plugins", icon: Puzzle },
      { href: "/audit", labelKey: "nav.audit", icon: ScrollText },
      { href: "/scheduler", labelKey: "nav.scheduler", icon: CalendarClock },
      { href: "/sandbox", labelKey: "nav.sandbox", icon: Container },
      { href: "/marketplace", labelKey: "nav.marketplace", icon: Store },
      { href: "/settings", labelKey: "nav.settings", icon: Settings },
    ],
  },
];

export function Sidebar() {
  const pathname = usePathname();
  const { locale, setLocale, t } = useI18n();

  return (
    <>
    <aside className="w-56 min-h-screen bg-gray-900 text-white flex flex-col">
      <div className="p-4 border-b border-gray-700 flex items-center justify-between">
        <div>
          <h1 className="text-lg font-bold text-indigo-400">Polsia</h1>
          <p className="text-xs text-gray-400">{t("brand.subtitle")}</p>
        </div>
        <NotificationBell />
      </div>
      <nav className="flex-1 p-3 space-y-4">
        {NAV_GROUPS.map((group) => (
          <div key={group.labelKey}>
            <p className="px-3 py-1 text-xs font-semibold uppercase tracking-wider text-gray-500">
              {t(group.labelKey)}
            </p>
            <div className="mt-1 space-y-1">
              {group.items.map(({ href, labelKey, icon: Icon }) => {
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
            </div>
          </div>
        ))}
      </nav>
      <div className="p-3 border-t border-gray-700 space-y-1">
        <button
          onClick={() => {
            // Dispatch Cmd+K to trigger GlobalSearch
            document.dispatchEvent(new KeyboardEvent("keydown", { key: "k", metaKey: true }));
          }}
          className="flex items-center gap-2 w-full px-3 py-2 rounded-md text-sm text-gray-300 hover:bg-gray-700 transition-colors"
        >
          <Search size={16} />
          {t("nav.search")}
        </button>
        <button
          onClick={() => setLocale(locale === "en" ? "zh" : "en")}
          className="flex items-center gap-2 w-full px-3 py-2 rounded-md text-sm text-gray-300 hover:bg-gray-700 transition-colors"
        >
          <Languages size={16} />
          {t("nav.lang")}
        </button>
      </div>
    </aside>
      <GlobalSearch />
    </>
  );
}
