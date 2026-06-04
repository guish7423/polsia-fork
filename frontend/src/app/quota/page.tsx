import { api, type QuotaData } from "@/lib/api";
import { PageTitle } from "@/components/PageTitle";
import { QuotaDonut } from "@/components/dashboard/QuotaDonut";

async function getQuota(): Promise<QuotaData | null> {
  try {
    return await api.get<QuotaData>("/quota");
  } catch {
    return null;
  }
}

const DIMENSION_CONFIG = [
  { key: "agents", color: "#818cf8", labelKey: "quota.agents" },   // indigo-400
  { key: "tasks", color: "#34d399", labelKey: "quota.tasks" },     // emerald-400
  { key: "tokens", color: "#fbbf24", labelKey: "quota.tokens" },   // amber-400
  { key: "cost", color: "#f472b6", labelKey: "quota.cost" },       // pink-400
] as const;

export default async function QuotaPage() {
  const quota = await getQuota();

  return (
    <div className="p-6 space-y-6">
      <PageTitle i18nKey="quota.title" />

      {!quota ? (
        <div className="bg-gray-800 rounded-lg p-6 text-center">
          <p className="text-gray-400">Failed to load quota data</p>
        </div>
      ) : (
        <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4">
          {DIMENSION_CONFIG.map((dim) => {
            const d = quota[dim.key];
            return (
              <QuotaDonut
                key={dim.key}
                labelKey={dim.labelKey}
                current={d.current}
                limit={d.limit}
                usagePct={d.usage_pct}
                color={dim.color}
                allowed={d.allowed}
              />
            );
          })}
        </div>
      )}
    </div>
  );
}
