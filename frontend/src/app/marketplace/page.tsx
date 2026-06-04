"use client";

import { useState, useEffect, useCallback } from "react";
import { api, type MarketplaceAgent } from "@/lib/api";
import { useI18n } from "@/lib/i18n";
import { PageTitle } from "@/components/PageTitle";

export default function MarketplacePage() {
  const { t } = useI18n();
  const [agents, setAgents] = useState<MarketplaceAgent[]>([]);
  const [loading, setLoading] = useState(true);
  const [search, setSearch] = useState("");
  const [actionBusy, setActionBusy] = useState<string | null>(null);

  const fetchAgents = useCallback(async () => {
    try {
      setLoading(true);
      const data = await api.get<MarketplaceAgent[]>("/marketplace/agents");
      setAgents(data);
    } catch {
      // fallback: API not available yet, show empty
      setAgents([]);
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    fetchAgents();
  }, [fetchAgents]);

  const install = async (name: string) => {
    setActionBusy(name);
    try {
      await api.post(`/marketplace/agents/${encodeURIComponent(name)}/install`);
      await fetchAgents();
    } catch {
      // silent for now
    } finally {
      setActionBusy(null);
    }
  };

  const uninstall = async (name: string) => {
    setActionBusy(name);
    try {
      await api.post(`/marketplace/agents/${encodeURIComponent(name)}/uninstall`);
      await fetchAgents();
    } catch {
      // silent
    } finally {
      setActionBusy(null);
    }
  };

  const filtered = agents.filter((a) => {
    if (!search) return true;
    const q = search.toLowerCase();
    return (
      a.name.toLowerCase().includes(q) ||
      a.type.toLowerCase().includes(q) ||
      a.description.toLowerCase().includes(q)
    );
  });

  const installed = filtered.filter((a) => a.installed);
  const available = filtered.filter((a) => !a.installed);

  return (
    <div className="p-6 space-y-6">
      {/* Header */}
      <div className="flex items-center justify-between">
        <PageTitle i18nKey="marketplace.title" />
      </div>

      {/* Search bar */}
      <div className="relative">
        <input
          type="text"
          value={search}
          onChange={(e) => setSearch(e.target.value)}
          placeholder={t("marketplace.search")}
          className="w-full bg-gray-800 border border-gray-700 rounded-lg px-4 py-2.5 pl-10 text-white placeholder-gray-500 text-sm focus:outline-none focus:ring-2 focus:ring-indigo-500 focus:border-transparent"
        />
        <svg
          className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-gray-500"
          fill="none"
          stroke="currentColor"
          viewBox="0 0 24 24"
        >
          <path
            strokeLinecap="round"
            strokeLinejoin="round"
            strokeWidth={2}
            d="M21 21l-4.35-4.35M11 19a8 8 0 100-16 8 8 0 000 16z"
          />
        </svg>
      </div>

      {/* Loading */}
      {loading && (
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
          {Array.from({ length: 6 }).map((_, i) => (
            <div key={i} className="h-36 bg-gray-800 rounded-lg animate-pulse" />
          ))}
        </div>
      )}

      {/* Empty */}
      {!loading && agents.length === 0 && (
        <div className="text-center py-16">
          <p className="text-gray-500 text-sm">{t("marketplace.empty")}</p>
        </div>
      )}

      {/* Installed section */}
      {!loading && installed.length > 0 && (
        <section>
          <h2 className="text-sm font-semibold text-gray-400 mb-3 uppercase tracking-wider">
            {t("marketplace.installed")} ({installed.length})
          </h2>
          <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
            {installed.map(renderCard)}
          </div>
        </section>
      )}

      {/* Available section */}
      {!loading && available.length > 0 && (
        <section>
          <h2 className="text-sm font-semibold text-gray-400 mb-3 uppercase tracking-wider">
            Available ({available.length})
          </h2>
          <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
            {available.map(renderCard)}
          </div>
        </section>
      )}
    </div>
  );

  function renderCard(a: MarketplaceAgent) {
    const busy = actionBusy === a.name;
    return (
      <div
        key={a.name}
        className="bg-gray-800 rounded-lg p-5 flex flex-col justify-between hover:bg-gray-750 transition-colors border border-gray-700/50"
      >
        <div>
          <div className="flex items-start justify-between gap-2">
            <div className="min-w-0 flex-1">
              <h3 className="text-white font-medium truncate">{a.name}</h3>
              <p className="text-xs text-gray-500 mt-0.5">{a.type}</p>
            </div>
            <span className="text-[10px] bg-gray-700 text-gray-400 px-1.5 py-0.5 rounded shrink-0">
              v{a.version}
            </span>
          </div>
          <p className="text-gray-400 text-sm mt-2 line-clamp-2">{a.description}</p>
        </div>

        <div className="mt-4 flex justify-end">
          {a.installed ? (
            <button
              onClick={() => uninstall(a.name)}
              disabled={busy}
              className="px-4 py-1.5 bg-red-600/20 hover:bg-red-600/30 disabled:opacity-50 disabled:cursor-not-allowed text-red-400 text-xs rounded-md transition-colors"
            >
              {busy ? "…" : t("marketplace.uninstall")}
            </button>
          ) : (
            <button
              onClick={() => install(a.name)}
              disabled={busy}
              className="px-4 py-1.5 bg-indigo-600 hover:bg-indigo-700 disabled:opacity-50 disabled:cursor-not-allowed text-white text-xs rounded-md transition-colors"
            >
              {busy ? "…" : t("marketplace.install")}
            </button>
          )}
        </div>
      </div>
    );
  }
}
