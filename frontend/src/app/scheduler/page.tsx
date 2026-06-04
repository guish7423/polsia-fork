"use client";

import { useEffect, useState, useCallback } from "react";
import { api, type SchedulerStatus } from "@/lib/api";
import { PageTitle } from "@/components/PageTitle";
import { MetricsCard } from "@/components/dashboard/MetricsCard";

export default function SchedulerPage() {
  const [status, setStatus] = useState<SchedulerStatus | null>(null);
  const [loading, setLoading] = useState(true);
  const [rebalancing, setRebalancing] = useState(false);
  const [message, setMessage] = useState<string | null>(null);
  const [msgType, setMsgType] = useState<"info" | "error">("info");

  const fetchStatus = useCallback(async () => {
    try {
      const data = await api.get<SchedulerStatus>("/scheduler/status");
      setStatus(data);
    } catch {
      // keep null
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    fetchStatus();
  }, [fetchStatus]);

  const handleRebalance = async () => {
    setRebalancing(true);
    setMessage(null);
    try {
      const result = await api.post<{ message: string }>("/scheduler/rebalance");
      setMessage(result.message);
      setMsgType("info");
      // Refresh status after rebalance
      await fetchStatus();
    } catch (e) {
      setMessage(String(e));
      setMsgType("error");
    } finally {
      setRebalancing(false);
    }
  };

  return (
    <div className="p-6 space-y-6">
      <PageTitle i18nKey="scheduler.title" />

      {/* Threshold warning */}
      {status?.threshold_exceeded && (
        <div className="rounded-lg px-4 py-3 text-sm bg-amber-900/50 border border-amber-500 text-amber-200">
          ⚠ Load threshold exceeded — rebalance recommended
        </div>
      )}

      {/* Notification */}
      {message && (
        <div
          className={`rounded-lg px-4 py-3 text-sm ${
            msgType === "error"
              ? "bg-red-900/50 border border-red-500 text-red-200"
              : "bg-indigo-900/50 border border-indigo-500 text-indigo-200"
          }`}
        >
          {message}
        </div>
      )}

      {/* Metric Cards */}
      <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
        <MetricsCard
          titleKey="scheduler.running"
          value={status?.running ?? "—"}
          loading={loading}
          trend={status && status.running > 0 ? "up" : undefined}
        />
        <MetricsCard
          titleKey="scheduler.pending"
          value={status?.pending ?? "—"}
          loading={loading}
        />
        <MetricsCard
          titleKey="scheduler.queued"
          value={status?.queued ?? "—"}
          loading={loading}
        />
        <MetricsCard
          titleKey="scheduler.load_score"
          value={status?.load_score != null ? `${status.load_score}%` : "—"}
          loading={loading}
          trend={
            status?.threshold_exceeded
              ? "down"
              : status && status.load_score > 0
                ? "up"
                : undefined
          }
          subtitle={
            status?.threshold_exceeded
              ? "Threshold exceeded"
              : `${status?.agents_limit ?? "?"} agent limit`
          }
        />
      </div>

      {/* Rebalance action */}
      <div className="flex items-center justify-between bg-gray-800 rounded-lg p-4">
        <div>
          <p className="text-sm text-gray-300">
            {status?.threshold_exceeded
              ? "System load is above optimal threshold. Rebalancing can redistribute tasks."
              : "Tasks are within normal operating parameters."}
          </p>
          {status && (
            <p className="text-xs text-gray-500 mt-1">
              {status.running + status.pending + status.queued} active tasks ·{" "}
              {status.agents_limit} agent slots
            </p>
          )}
        </div>
        <button
          onClick={handleRebalance}
          disabled={rebalancing}
          className="px-5 py-2 bg-indigo-600 hover:bg-indigo-700 disabled:opacity-50 disabled:cursor-not-allowed text-white text-sm rounded-md transition-colors whitespace-nowrap ml-4"
        >
          {rebalancing ? "Rebalancing…" : "Rebalance"}
        </button>
      </div>
    </div>
  );
}
