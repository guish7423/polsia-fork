"use client";

import { useState, useEffect, useCallback, useRef } from "react";
import { api, type DashboardHealth } from "@/lib/api";
import { useI18n } from "@/lib/i18n";

const POLL_INTERVAL = 30_000;

const OVERALL_STYLES: Record<string, { dot: string; label: string; text: string }> = {
  healthy: { dot: "bg-green-400", label: "health.all_operational", text: "text-green-400" },
  degraded: { dot: "bg-yellow-400", label: "health.degraded", text: "text-yellow-400" },
  down: { dot: "bg-red-500", label: "health.down", text: "text-red-400" },
};

const CHECK_ICONS: Record<string, string> = {
  healthy: "✅",
  degraded: "⚠️",
  warning: "⚡",
};

function formatCheckValue(key: string, check: Record<string, unknown>): string {
  switch (key) {
    case "agents":
      return `${check.running ?? "?"} running · ${check.errored ?? 0} errors`;
    case "tasks":
      return `${check.pending ?? "?"} pending · ${check.failed_24h ?? 0} failed (24h)`;
    case "quota":
      return `avg ${check.avg_usage_pct ?? "?"}% used`;
    case "cost":
      return `$${check.cost_24h_usd ?? "0"} (24h)`;
    default:
      return "";
  }
}

export function SystemHealthCard() {
  const { t } = useI18n();
  const [health, setHealth] = useState<DashboardHealth | null>(null);
  const [loading, setLoading] = useState(true);
  const intervalRef = useRef<ReturnType<typeof setInterval> | null>(null);

  const fetchHealth = useCallback(async () => {
    try {
      const data = await api.get<DashboardHealth>("/dashboard/health");
      setHealth(data);
    } catch {
      // fail-open: keep current state or show degraded
      if (!health) {
        setHealth({
          overall: "degraded",
          checks: {
            agents: { status: "degraded" },
            tasks: { status: "degraded" },
            quota: { status: "degraded" },
            cost: { status: "degraded", cost_24h_usd: 0, budget_pct: 0 },
            last_updated: new Date().toISOString(),
          },
        });
      }
    } finally {
      setLoading(false);
    }
  }, [health]);

  useEffect(() => {
    fetchHealth();
    intervalRef.current = setInterval(fetchHealth, POLL_INTERVAL);
    return () => {
      if (intervalRef.current) clearInterval(intervalRef.current);
    };
  }, [fetchHealth]);

  if (loading) return null;

  const overallKey = health?.overall ?? "degraded";
  const styles = OVERALL_STYLES[overallKey] ?? OVERALL_STYLES.degraded;
  const checks = health?.checks;

  return (
    <div className="bg-gray-800 rounded-lg p-4 text-sm">
      {/* Header: big dot + overall status */}
      <div className="flex items-center gap-3 mb-4">
        <div
          data-testid="health-dot"
          className={`w-4 h-4 rounded-full ${styles.dot} shadow-lg`}
        />
        <span className={`font-semibold text-base ${styles.text}`}>
          {t(styles.label)}
        </span>
      </div>

      {/* Check rows */}
      {checks && (
        <div className="space-y-2">
          {["agents", "tasks", "quota", "cost"].map((key) => {
            const check = checks[key as keyof typeof checks] as Record<string, unknown> | undefined;
            if (!check) return null;
            const status = (check.status as string) ?? "healthy";
            const icon = CHECK_ICONS[status] ?? "❓";
            const label = t(`health.${key}`);
            const value = formatCheckValue(key, check);

            return (
              <div key={key} className="flex items-center justify-between text-gray-300">
                <div className="flex items-center gap-2">
                  <span className="text-xs">{icon}</span>
                  <span>{label}</span>
                </div>
                <span className="text-gray-400 text-xs truncate ml-2 max-w-[180px]">
                  {value}
                </span>
              </div>
            );
          })}

          {/* Last updated */}
          <div className="flex items-center justify-between text-gray-500 pt-1 border-t border-gray-700 mt-2">
            <span>{t("health.last_updated")}</span>
            <span className="text-xs">
              {checks.last_updated
                ? new Date(checks.last_updated).toLocaleTimeString()
                : "—"}
            </span>
          </div>
        </div>
      )}
    </div>
  );
}
