"use client";

import { useI18n } from "@/lib/i18n";
import { api, type SandboxSummary, type SandboxExecution } from "@/lib/api";
import { PageTitle, Text } from "@/components/PageTitle";
import { useEffect, useState } from "react";

function SummaryCard({
  labelKey,
  value,
  color,
}: {
  labelKey: string;
  value: number;
  color: string;
}) {
  return (
    <div className="bg-gray-800 rounded-lg p-4 flex flex-col gap-1">
      <span className="text-gray-400 text-xs">
        <Text i18nKey={labelKey} />
      </span>
      <span className={`text-2xl font-bold ${color}`}>{value}</span>
    </div>
  );
}

const STATUS_STYLE: Record<string, string> = {
  approved: "bg-green-500/20 text-green-400",
  rejected: "bg-red-500/20 text-red-400",
  pending: "bg-yellow-500/20 text-yellow-400",
  running: "bg-blue-500/20 text-blue-400",
};

function StatusBadge({ status }: { status: string }) {
  const { t } = useI18n();
  const key = `sandbox.${status}`;
  const label = t(key) !== key ? t(key) : status;
  return (
    <span
      className={`px-2 py-1 rounded text-xs font-medium ${
        STATUS_STYLE[status] ?? "bg-gray-700 text-gray-400"
      }`}
    >
      {label}
    </span>
  );
}

function ExecutionRow({
  exec,
  isExpanded,
  onToggle,
}: {
  exec: SandboxExecution;
  isExpanded: boolean;
  onToggle: () => void;
}) {
  const { t } = useI18n();
  return (
    <>
      <tr
        className="border-b border-gray-700/50 hover:bg-gray-800/40 cursor-pointer transition-colors"
        onClick={onToggle}
      >
        <td className="py-3 px-2 text-white text-sm">
          {exec.action_type.replace(/_/g, " ")}
        </td>
        <td className="py-3 px-2">
          <StatusBadge status={exec.status} />
        </td>
        <td className="py-3 px-2 text-gray-300 text-sm">
          {new Date(exec.created_at).toLocaleString()}
        </td>
        <td className="py-3 px-2 text-gray-400 text-xs">
          {exec.agent_type}
        </td>
        <td className="py-3 px-2 text-right">
          <span className="text-gray-500 text-sm">
            {isExpanded ? "▲" : "▼"}
          </span>
        </td>
      </tr>
      {isExpanded && (
        <tr className="bg-gray-800/30">
          <td colSpan={5} className="p-4">
            <div className="space-y-2 text-sm">
              {exec.summary && (
                <p className="text-gray-300">
                  <span className="text-gray-500 font-medium">Summary:</span>{" "}
                  {exec.summary}
                </p>
              )}
              {exec.rule_id && (
                <p className="text-gray-400">
                  <span className="text-gray-500 font-medium">
                    {t("sandbox.rule") ?? "Rule ID"}:
                  </span>{" "}
                  <code className="text-purple-400">{exec.rule_id}</code>
                </p>
              )}
              {exec.payload && Object.keys(exec.payload).length > 0 && (
                <div>
                  <span className="text-gray-500 font-medium">
                    {t("sandbox.payload") ?? "Payload"}:
                  </span>
                  <pre className="text-gray-400 bg-gray-900/60 rounded p-2 mt-1 overflow-x-auto text-xs">
                    {JSON.stringify(exec.payload, null, 2)}
                  </pre>
                </div>
              )}
            </div>
          </td>
        </tr>
      )}
    </>
  );
}

export default function SandboxPage() {
  const { t } = useI18n();
  const [data, setData] = useState<SandboxSummary | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [expandedId, setExpandedId] = useState<number | null>(null);

  useEffect(() => {
    setLoading(true);
    setError(null);
    api
      .get<SandboxSummary>("/sandbox/summary")
      .then(setData)
      .catch((e) => {
        console.error("Failed to load sandbox summary:", e);
        setError(e instanceof Error ? e.message : "Unknown error");
      })
      .finally(() => setLoading(false));
  }, []);

  return (
    <div className="p-6 space-y-6">
      <PageTitle i18nKey="sandbox.title" />

      {/* Summary cards */}
      <div className="grid grid-cols-4 gap-4">
        <SummaryCard
          labelKey="sandbox.pending"
          value={data?.pending_approval ?? 0}
          color="text-yellow-400"
        />
        <SummaryCard
          labelKey="sandbox.approved"
          value={data?.approved ?? 0}
          color="text-green-400"
        />
        <SummaryCard
          labelKey="sandbox.rejected"
          value={data?.total_rejected ?? 0}
          color="text-red-400"
        />
        <div className="bg-gray-800 rounded-lg p-4 flex flex-col gap-1">
          <span className="text-gray-400 text-xs">
            {t("sandbox.sandbox_enabled") ?? "Sandbox"}
          </span>
          <span
            className={`text-2xl font-bold ${
              data?.sandbox_enabled ? "text-green-400" : "text-gray-500"
            }`}
          >
            {data?.sandbox_enabled
              ? t("sandbox.enabled") ?? "Enabled"
              : t("sandbox.disabled") ?? "Disabled"}
          </span>
        </div>
      </div>

      {/* Execution table */}
      {loading && <p className="text-gray-400">{t("settings.loading")}</p>}
      {error && <p className="text-red-400">Error: {error}</p>}
      {!loading && !error && (!data?.recent || data.recent.length === 0) && (
        <p className="text-gray-400">
          <Text i18nKey="sandbox.empty" />
        </p>
      )}
      {!loading && !error && data?.recent && data.recent.length > 0 && (
        <div className="bg-gray-800/50 rounded-lg overflow-hidden">
          <table className="w-full">
            <thead>
              <tr className="border-b border-gray-700 text-xs text-gray-500 uppercase tracking-wider">
                <th className="text-left py-3 px-2 font-medium">
                  {t("sandbox.action") ?? "Action"}
                </th>
                <th className="text-left py-3 px-2 font-medium">
                  {t("sandbox.status") ?? "Status"}
                </th>
                <th className="text-left py-3 px-2 font-medium">
                  {t("sandbox.created_at") ?? "Created At"}
                </th>
                <th className="text-left py-3 px-2 font-medium">
                  {t("sandbox.agent") ?? "Agent"}
                </th>
                <th className="py-3 px-2" />
              </tr>
            </thead>
            <tbody>
              {data.recent.map((exec) => (
                <ExecutionRow
                  key={exec.id}
                  exec={exec}
                  isExpanded={expandedId === exec.id}
                  onToggle={() =>
                    setExpandedId(expandedId === exec.id ? null : exec.id)
                  }
                />
              ))}
            </tbody>
          </table>
        </div>
      )}
    </div>
  );
}
