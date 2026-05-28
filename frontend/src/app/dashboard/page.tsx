import { ActivityFeed } from "@/components/dashboard/ActivityFeed";
import { AgentStatusGrid } from "@/components/dashboard/AgentStatusGrid";
import { MetricsCard } from "@/components/dashboard/MetricsCard";
import { api, type DashboardSummary } from "@/lib/api";
import { PageTitle, SectionTitle } from "@/components/PageTitle";

async function getSummary(): Promise<DashboardSummary | null> {
  try {
    return await api.get<DashboardSummary>("/dashboard/summary");
  } catch {
    return null;
  }
}

export default async function DashboardPage() {
  const summary = await getSummary();
  const kpis = summary?.kpis ?? {};

  return (
    <div className="p-6 space-y-6">
      <PageTitle i18nKey="dash.title" />

      {/* KPI Cards */}
      <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
        <MetricsCard
          titleKey="dash.tasks_today"
          value={summary?.tasks_today_total ?? "—"}
          subtitle={`${summary?.tasks_today_completed ?? 0} ✓ · ${summary?.tasks_today_failed ?? 0} ✗`}
        />
        <MetricsCard
          titleKey="dash.mrr"
          value={kpis.mrr_usd != null ? `$${kpis.mrr_usd}` : "—"}
          trend="up"
        />
        <MetricsCard
          titleKey="dash.active_customers"
          value={kpis.active_customers != null ? String(kpis.active_customers) : "—"}
        />
        <MetricsCard
          titleKey="dash.churn_rate"
          value={kpis.churn_rate != null ? `${kpis.churn_rate}%` : "—"}
          trend={Number(kpis.churn_rate) > 5 ? "down" : "neutral"}
        />
      </div>

      {/* Agent Grid + Activity Feed */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        <div>
          <SectionTitle i18nKey="dash.agent_status" />
          <AgentStatusGrid />
        </div>
        <div className="h-96">
          <SectionTitle i18nKey="dash.live_activity" />
          <ActivityFeed />
        </div>
      </div>
    </div>
  );
}


