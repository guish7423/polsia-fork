import { MetricsCard } from "@/components/dashboard/MetricsCard";
import { api, type FinanceSummary } from "@/lib/api";
import { PageTitle, Text } from "@/components/PageTitle";

async function getFinanceSummary(): Promise<FinanceSummary | null> {
  try {
    return await api.get<FinanceSummary>("/finance/summary");
  } catch {
    return null;
  }
}

function formatCents(cents: number): string {
  return `$${(cents / 100).toLocaleString("en-US", { minimumFractionDigits: 2, maximumFractionDigits: 2 })}`;
}

export default async function FinancePage() {
  const summary = await getFinanceSummary();

  return (
    <div className="p-6 space-y-6">
      <div className="flex items-center justify-between">
        <PageTitle i18nKey="finance.title" />
        {summary?.last_snapshot_date && (
          <p className="text-gray-400 text-sm"><Text i18nKey="finance.last_snapshot" />: {summary.last_snapshot_date}</p>
        )}
      </div>

      <div className="grid grid-cols-2 md:grid-cols-3 gap-4">
        <MetricsCard titleKey="dash.mrr" value={summary ? formatCents(summary.mrr_cents) : "—"} trend="up" />
        <MetricsCard titleKey="finance.arr" value={summary ? formatCents(summary.arr_cents) : "—"} trend="up" />
        <MetricsCard titleKey="finance.active_subscribers" value={summary?.active_subscribers ?? "—"} />
        <MetricsCard titleKey="finance.stripe_balance" value={summary ? formatCents(summary.stripe_balance_cents) : "—"} />
        <MetricsCard titleKey="finance.total_ad_spend" value={summary ? `$${summary.total_ad_spend_usd.toFixed(2)}` : "—"} trend="neutral" />
        <MetricsCard titleKey="finance.expenses_month" value={summary ? formatCents(summary.total_expenses_month_cents) : "—"} trend="neutral" />
      </div>
    </div>
  );
}
