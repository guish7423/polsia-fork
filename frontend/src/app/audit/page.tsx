"use client";
import { useEffect, useState, useCallback } from "react";
import { api, type AuditEntry } from "@/lib/api";
import { useI18n } from "@/lib/i18n";

export default function AuditPage() {
  const { t } = useI18n();
  const [entries, setEntries] = useState<AuditEntry[]>([]);
  const [loading, setLoading] = useState(true);
  const [verifying, setVerifying] = useState(false);
  const [integrity, setIntegrity] = useState<{ intact: boolean; broken_links: string[] } | null>(null);

  const fetchEntries = useCallback(async () => {
    setLoading(true);
    try {
      const data = await api.get<{ entries: AuditEntry[]; total: number }>("/audit/entries?limit=100");
      setEntries(data.entries);
    } catch {
      setEntries([]);
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    fetchEntries();
  }, [fetchEntries]);

  const verifyChain = useCallback(async () => {
    setVerifying(true);
    setIntegrity(null);
    try {
      const result = await api.get<{ intact: boolean; broken_links: string[] }>("/audit/verify");
      setIntegrity(result);
    } catch {
      setIntegrity({ intact: false, broken_links: [] });
    } finally {
      setVerifying(false);
    }
  }, []);

  const hashPreview = (hash: string) => `${hash.slice(0, 8)}…${hash.slice(-6)}`;

  return (
    <div className="p-6 space-y-6">
      <div className="flex items-center justify-between">
        <h1 className="text-2xl font-bold text-white">{t("audit.title")}</h1>
        <button
          onClick={verifyChain}
          disabled={verifying}
          className="px-4 py-2 bg-indigo-600 hover:bg-indigo-700 disabled:opacity-50 text-white rounded-md text-sm font-medium"
        >
          {verifying ? "…" : t("audit.verify")}
        </button>
      </div>

      {/* Integrity result banner */}
      {integrity !== null && (
        <div
          className={`rounded-lg px-4 py-3 text-sm ${
            integrity.intact
              ? "bg-green-900/50 border border-green-500 text-green-300"
              : "bg-red-900/50 border border-red-500 text-red-300"
          }`}
        >
          {integrity.intact ? t("audit.intact") : t("audit.broken")}
        </div>
      )}

      {/* Entries table */}
      <div className="bg-gray-800 rounded-lg overflow-hidden">
        {loading ? (
          <div className="p-6 text-center text-gray-400">{t("settings.loading")}</div>
        ) : entries.length === 0 ? (
          <div className="p-6 text-center text-gray-400">{t("audit.empty")}</div>
        ) : (
          <div className="overflow-x-auto">
            <table className="w-full text-sm">
              <thead>
                <tr className="border-b border-gray-700 text-gray-400 text-left">
                  <th className="px-4 py-3 font-medium">ID</th>
                  <th className="px-4 py-3 font-medium">{t("memory.category")}</th>
                  <th className="px-4 py-3 font-medium">Action</th>
                  <th className="px-4 py-3 font-medium">Hash</th>
                  <th className="px-4 py-3 font-medium">Previous</th>
                  <th className="px-4 py-3 font-medium">Date</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-gray-700">
                {entries.map((entry) => (
                  <tr key={entry.id} className="hover:bg-gray-750 text-white">
                    <td className="px-4 py-3 text-gray-400">{entry.id}</td>
                    <td className="px-4 py-3">
                      <span className="text-indigo-300">{entry.entry_type}</span>
                      <span className="text-gray-500"> #{entry.entry_id}</span>
                    </td>
                    <td className="px-4 py-3">{entry.action}</td>
                    <td className="px-4 py-3 font-mono text-xs text-gray-400" title={entry.hash}>
                      {hashPreview(entry.hash)}
                    </td>
                    <td className="px-4 py-3 font-mono text-xs text-gray-500" title={entry.previous_hash}>
                      {entry.previous_hash === "0000000000000000000000000000000000000000000000000000000000000000"
                        ? "—"
                        : hashPreview(entry.previous_hash)}
                    </td>
                    <td className="px-4 py-3 text-gray-400 whitespace-nowrap">
                      {entry.created_at ? new Date(entry.created_at).toLocaleString() : "—"}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </div>
    </div>
  );
}
