"use client";
import { useAgentStatus } from "@/hooks/useAgentStatus";

const STATUS_BADGE: Record<string, string> = {
  idle: "bg-gray-600/40 text-gray-300",
  running: "bg-green-500/20 text-green-400 animate-pulse",
  error: "bg-red-500/20 text-red-400",
};

const SHORT_LABELS: Record<string, string> = {
  orchestrator: "CEO",
  supervisor: "Plan",
  business_planning: "Strategy",
  competitor_research: "Research",
  social_media: "Social",
  ads_management: "Ads",
  email_outreach: "Email",
  code_generation: "Code",
  customer_support: "Support",
  finance: "Finance",
  lead_nurturing: "Leads",
  order_scanner: "Scanner",
  order_fulfiller: "Fulfill",
  market_intel: "Intel",
  monitor: "Watchdog",
  evolution: "Evolve",
  deploy_agent: "Deploy",
  deployment: "DevOps",
};

export function AgentStatusGrid() {
  const { agents, loading, runningCount, todayStats } = useAgentStatus();

  if (loading) {
    return (
      <div className="grid grid-cols-3 gap-3">
        {Array.from({ length: 9 }).map((_, i) => (
          <div key={i} className="h-20 bg-gray-700 rounded-lg animate-pulse" />
        ))}
      </div>
    );
  }

  return (
    <div>
      {/* Summary bar */}
      <div className="flex items-center gap-4 mb-4 text-xs text-gray-400">
        <span>
          <span className="text-white font-medium">{agents.length}</span> agents
        </span>
        <span>
          <span className="text-green-400 font-medium">{runningCount}</span> running
        </span>
        <span>
          <span className="text-white font-medium">{todayStats.totalRuns}</span> runs today
        </span>
        <span>
          <span className="text-amber-400 font-medium">
            ${todayStats.totalCost.toFixed(4)}
          </span> cost
        </span>
      </div>

      <div className="grid grid-cols-3 gap-3">
        {agents.map((a) => {
          const style = STATUS_BADGE[a.status] ?? STATUS_BADGE.idle;
          const label = SHORT_LABELS[a.agent_type] ?? a.agent_type.replace(/_/g, " ");

          return (
            <div key={a.agent_type} className="bg-gray-800 rounded-lg p-3">
              <div className="flex items-center justify-between">
                <p className="text-white text-sm font-medium capitalize">{label}</p>
                <span className={`inline-block px-2 py-0.5 rounded text-xs ${style}`}>
                  {a.status}
                </span>
              </div>
              <div className="mt-2 flex gap-3 text-xs text-gray-400">
                <span>{a.today.run_count} runs</span>
                {a.today.total_cost_usd > 0 && (
                  <span>${a.today.total_cost_usd.toFixed(4)}</span>
                )}
              </div>
              {a.last_run && (
                <p className="text-gray-500 text-[10px] mt-1 truncate">
                  {a.last_run.status} · {a.last_run.duration_secs?.toFixed(0) ?? "?"}s
                </p>
              )}
            </div>
          );
        })}
      </div>
    </div>
  );
}
