"use client";
import { ActivityFeed } from "@/components/dashboard/ActivityFeed";
import { AgentStatusGrid } from "@/components/dashboard/AgentStatusGrid";
import { GlobalAlertBanner } from "@/components/dashboard/GlobalAlertBanner";
import { MetricsCard } from "@/components/dashboard/MetricsCard";
import { SystemHealthCard } from "@/components/dashboard/SystemHealthCard";
import { useDashboardRefresh } from "@/hooks/useDashboardRefresh";

export default function DashboardPage() {
  const { summary, lastUpdated } = useDashboardRefresh(30000);
  const kpis = summary?.kpis ?? {};

  return (
    <div className="p-6 space-y-6">
      {/* Global Alert Banner — full width, top of page */}
      <GlobalAlertBanner />

      {/* Title row with last-updated + HealthCard */}
      <div className="flex items-start justify-between gap-6">
        <div className="flex items-center gap-4">
          <h1 className="text-2xl font-bold text-white">Dashboard</h1>
          {lastUpdated && (
            <span className="text-xs text-gray-500 mt-1">
              Last updated: {lastUpdated}
            </span>
          )}
        </div>
        <div className="w-72 flex-shrink-0">
          <SystemHealthCard />
        </div>
      </div>

      {/* KPI Cards */}
      <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
        <MetricsCard
          title="Tasks Today"
          value={summary?.tasks_today_total ?? "—"}
          subtitle={`${summary?.tasks_today_completed ?? 0} completed · ${summary?.tasks_today_failed ?? 0} failed`}
        />
        <MetricsCard
          title="MRR"
          value={kpis.mrr_usd != null ? `$${kpis.mrr_usd}` : "—"}
          trend="up"
        />
        <MetricsCard
          title="Active Customers"
          value={kpis.active_customers != null ? String(kpis.active_customers) : "—"}
        />
        <MetricsCard
          title="Churn Rate"
          value={kpis.churn_rate != null ? `${kpis.churn_rate}%` : "—"}
          trend={Number(kpis.churn_rate) > 5 ? "down" : "neutral"}
        />
      </div>

      {/* Agent Grid + Activity Feed */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        <div>
          <h2 className="text-sm font-semibold text-gray-400 mb-3 uppercase tracking-wider">
            Agent Status
          </h2>
          <AgentStatusGrid />
        </div>
        <div className="h-96">
          <h2 className="text-sm font-semibold text-gray-400 mb-3 uppercase tracking-wider">
            Live Activity
          </h2>
          <ActivityFeed />
        </div>
      </div>
    </div>
  );
}
