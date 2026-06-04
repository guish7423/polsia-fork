"use client";
import { useEffect, useState, useRef } from "react";
import { api, type DashboardSummary } from "@/lib/api";

export function useDashboardRefresh(pollIntervalMs = 30000) {
  const [summary, setSummary] = useState<DashboardSummary | null>(null);
  const [lastUpdated, setLastUpdated] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);

  // Keep a ref to the latest fetch function so setInterval always calls the current one
  const fetchRef = useRef(async () => {
    try {
      const data = await api.get<DashboardSummary>("/dashboard/summary");
      setSummary(data);
      setLastUpdated(new Date().toLocaleTimeString());
      setError(null);
    } catch (e) {
      setError(String(e));
    }
  });

  // Keep the ref current on every render
  fetchRef.current = async () => {
    try {
      const data = await api.get<DashboardSummary>("/dashboard/summary");
      setSummary(data);
      setLastUpdated(new Date().toLocaleTimeString());
      setError(null);
    } catch (e) {
      setError(String(e));
    }
  };

  useEffect(() => {
    let cancelled = false;

    const tick = async () => {
      await fetchRef.current();
    };

    // Initial fetch
    tick();

    // Periodic polling
    const interval = setInterval(tick, pollIntervalMs);
    return () => {
      cancelled = true;
      clearInterval(interval);
    };
  }, [pollIntervalMs]);

  return { summary, lastUpdated, error };
}
