"use client";

import { useState, useEffect, useCallback, useRef } from "react";
import { api, type ActiveAlert, type AlertSeverity } from "@/lib/api";
import { useI18n } from "@/lib/i18n";

const POLL_INTERVAL = 30_000;
const RE_CHECK_DELAY = 120_000;

const SEVERITY_STYLES: Record<AlertSeverity, string> = {
  critical: "bg-red-600/90 border-red-400 text-white",
  warning: "bg-yellow-500/90 border-yellow-400 text-black",
  info: "bg-blue-500/90 border-blue-400 text-white",
};

const SEVERITY_ICON: Record<AlertSeverity, string> = {
  critical: "🔴",
  warning: "⚠️",
  info: "ℹ️",
};

function sortBySeverity(alerts: ActiveAlert[]): ActiveAlert[] {
  const order: Record<AlertSeverity, number> = { critical: 0, warning: 1, info: 2 };
  return [...alerts].sort(
    (a, b) => (order[a.severity] ?? 9) - (order[b.severity] ?? 9),
  );
}

export function GlobalAlertBanner() {
  const { t } = useI18n();
  const [alerts, setAlerts] = useState<ActiveAlert[]>([]);
  const [dismissedIds, setDismissedIds] = useState<Set<number>>(new Set());
  const intervalRef = useRef<ReturnType<typeof setInterval> | null>(null);

  const fetchAlerts = useCallback(async () => {
    try {
      const data = await api.get<{ alerts: ActiveAlert[]; total: number }>("/alerts/active");
      setAlerts(data.alerts);
    } catch {
      // fail-open: keep current state
    }
  }, []);

  useEffect(() => {
    fetchAlerts();
    intervalRef.current = setInterval(fetchAlerts, POLL_INTERVAL);
    return () => {
      if (intervalRef.current) clearInterval(intervalRef.current);
    };
  }, [fetchAlerts]);

  // Re-check dismissed critical alerts after RE_CHECK_DELAY
  const handleDismiss = useCallback(
    (alertId: number, severity: AlertSeverity) => {
      setDismissedIds((prev) => new Set(prev).add(alertId));
      if (severity === "critical") {
        setTimeout(() => {
          setDismissedIds((prev) => {
            const next = new Set(prev);
            next.delete(alertId);
            return next;
          });
        }, RE_CHECK_DELAY);
      }
    },
    [],
  );

  const visible = alerts.filter((a) => !dismissedIds.has(a.id));
  if (visible.length === 0) return null;

  const sorted = sortBySeverity(visible);
  // Show banner style from the most severe alert
  const topSeverity = sorted[0].severity;

  // Info severity: only show briefly (simulate first-time display)
  // by ignoring info-only banners after first render
  if (topSeverity === "info" && sorted.every((a) => a.severity === "info")) {
    return null;
  }

  return (
    <div
      role="alert"
      className={`px-4 py-2 border-b ${SEVERITY_STYLES[topSeverity]} flex items-center justify-between text-sm`}
    >
      <div className="flex items-center gap-2 flex-1 min-w-0">
        <span>{SEVERITY_ICON[topSeverity]}</span>
        {visible.length === 1 ? (
          <span className="truncate">{sorted[0].message}</span>
        ) : (
          <span>
            {t("alert.alert_count").replace("{count}", String(visible.length))}
          </span>
        )}
      </div>
      <div className="flex items-center gap-3 flex-shrink-0 ml-4">
        {visible.length === 1 && (
          <span className="text-xs opacity-70">
            {visible[0].source} · {visible[0].alert_type}
          </span>
        )}
        {topSeverity !== "info" && (
          <button
            onClick={() => {
              // Dismiss all non-info visible alerts
              visible.forEach((a) => handleDismiss(a.id, a.severity));
            }}
            className="text-xs underline hover:no-underline opacity-80 hover:opacity-100 whitespace-nowrap"
          >
            {t("alert.dismiss")}
          </button>
        )}
      </div>
    </div>
  );
}
