"use client";
import { useState } from "react";
import { useAgentStatus } from "@/hooks/useAgentStatus";
import { api } from "@/lib/api";
import { useI18n } from "@/lib/i18n";
import { PageTitle } from "@/components/PageTitle";

const AGENT_DESCRIPTIONS: Record<string, string> = {
  orchestrator: "agent.orchestrator",
  business_planning: "agent.business_planning",
  competitor_research: "agent.competitor_research",
  social_media: "agent.social_media",
  ads_management: "agent.ads_management",
  email_outreach: "agent.email_outreach",
  code_generation: "agent.code_generation",
  customer_support: "agent.customer_support",
  finance: "agent.finance",
};

export default function AgentsPage() {
  const { statuses, loading } = useAgentStatus();
  const { t } = useI18n();
  const [triggering, setTriggering] = useState<string | null>(null);
  const [message, setMessage] = useState<string | null>(null);

  const trigger = async (agentType: string) => {
    setTriggering(agentType);
    setMessage(null);
    try {
      const result = await api.post<{ message: string }>(`/agents/${agentType}/trigger`);
      setMessage(result.message);
    } catch (e) {
      setMessage(String(e));
    } finally {
      setTriggering(null);
    }
  };

  return (
    <div className="p-6 space-y-6">
      <div className="flex items-center justify-between">
        <PageTitle i18nKey="agents.title" />
      </div>

      {message && (
        <div className="bg-indigo-900/50 border border-indigo-500 rounded-lg px-4 py-3 text-indigo-200 text-sm">
          {message}
        </div>
      )}

      {loading ? (
        <div className="space-y-3">
          {Array.from({ length: 9 }).map((_, i) => (
            <div key={i} className="h-20 bg-gray-800 rounded-lg animate-pulse" />
          ))}
        </div>
      ) : (
        <div className="space-y-3">
          {statuses.map((s) => (
            <div
              key={s.agent_type}
              className="bg-gray-800 rounded-lg p-4 flex items-center justify-between"
            >
              <div>
                <h3 className="text-white font-medium capitalize">
                  {s.agent_type.replace(/_/g, " ")}
                </h3>
                <p className="text-gray-400 text-sm">
                  {t(AGENT_DESCRIPTIONS[s.agent_type] ?? "")}
                </p>
                <p className="text-gray-500 text-xs mt-1">
                  {t("agents.last_run")}: {s.last_run_at ? new Date(s.last_run_at).toLocaleString() : t("agents.never")} ·{" "}
                  {s.tasks_today} {t("agents.tasks_today")}
                </p>
              </div>
              <button
                onClick={() => trigger(s.agent_type)}
                disabled={triggering === s.agent_type}
                className="px-4 py-2 bg-indigo-600 hover:bg-indigo-700 disabled:opacity-50 text-white text-sm rounded-md transition-colors"
              >
                {triggering === s.agent_type ? t("agents.triggering") : t("agents.run_now")}
              </button>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}
