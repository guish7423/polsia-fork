"use client";
import { useEffect, useState } from "react";
import { api, type AgentMonitorEntry } from "@/lib/api";

export function useAgentStatus(pollIntervalMs = 30000) {
  const [agents, setAgents] = useState<AgentMonitorEntry[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    let cancelled = false;

    const fetch = async () => {
      try {
        const data = await api.get<AgentMonitorEntry[]>("/agents/monitor");
        if (!cancelled) {
          setAgents(data);
          setError(null);
        }
      } catch (e) {
        if (!cancelled) setError(String(e));
      } finally {
        if (!cancelled) setLoading(false);
      }
    };

    fetch();
    const interval = setInterval(fetch, pollIntervalMs);
    return () => {
      cancelled = true;
      clearInterval(interval);
    };
  }, [pollIntervalMs]);

  /** Derived: running agents count */
  const runningCount = agents.filter((a) => a.status === "running").length;

  /** Derived: today's stats */
  const todayStats = {
    totalRuns: agents.reduce((s, a) => s + a.today.run_count, 0),
    totalCost: agents.reduce((s, a) => s + a.today.total_cost_usd, 0),
  };

  return { agents, loading, error, runningCount, todayStats };
}
