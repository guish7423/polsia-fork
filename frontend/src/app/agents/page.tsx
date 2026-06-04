"use client";
import { useState } from "react";
import Link from "next/link";
import { useAgentStatus } from "@/hooks/useAgentStatus";
import { api } from "@/lib/api";
import { PageTitle } from "@/components/PageTitle";
import { FlowLog } from "@/components/agents/FlowLog";

const STATUS_STYLE: Record<string, string> = {
  idle: "bg-gray-600/40 text-gray-300",
  running: "bg-green-500/20 text-green-400 animate-pulse border border-green-500/30",
  error: "bg-red-500/20 text-red-400",
};

const TIER_BADGE: Record<string, string> = {
  orchestrator: "CORE",
  supervisor: "CORE",
  evolution: "CORE",
  monitor: "CORE",
  market_intel: "CORE",
};

export default function AgentsPage() {
  const { agents, loading, todayStats } = useAgentStatus(15000); // Poll every 15s
  const [triggering, setTriggering] = useState<string | null>(null);
  const [message, setMessage] = useState<string | null>(null);
  const [liveLogAgent, setLiveLogAgent] = useState<string | null>(null);
  const [msgType, setMsgType] = useState<"info" | "error">("info");

  const trigger = async (agentType: string) => {
    setTriggering(agentType);
    setMessage(null);
    try {
      const result = await api.post<{ message: string }>(`/agents/${agentType}/trigger`);
      setMessage(result.message);
      setMsgType("info");
    } catch (e) {
      setMessage(String(e));
      setMsgType("error");
    } finally {
      setTriggering(null);
    }
  };

  // Group by status
  const running = agents.filter((a) => a.status === "running");
  const idle = agents.filter((a) => a.status === "idle");
  const errored = agents.filter((a) => a.status === "error");

  return (
    <div className="p-6 space-y-6">
      {/* Header */}
      <div className="flex items-center justify-between">
        <PageTitle i18nKey="agents.title" />
        <div className="flex items-center gap-4 text-sm">
          <Link
            href="/agents/runs"
            className="text-indigo-400 hover:text-indigo-300 transition-colors"
          >
            Run History →
          </Link>
        </div>
      </div>

      {/* Today's summary bar */}
      <div className="bg-gray-800 rounded-lg p-4 flex items-center gap-8 text-sm">
        <div>
          <p className="text-gray-400 text-xs">Total Agents</p>
          <p className="text-white text-xl font-semibold">{agents.length}</p>
        </div>
        <div>
          <p className="text-gray-400 text-xs">Running Now</p>
          <p className="text-green-400 text-xl font-semibold">{running.length}</p>
        </div>
        <div>
          <p className="text-gray-400 text-xs">Runs Today</p>
          <p className="text-white text-xl font-semibold">{todayStats.totalRuns}</p>
        </div>
        <div>
          <p className="text-gray-400 text-xs">Cost Today</p>
          <p className="text-amber-400 text-xl font-semibold">
            ${todayStats.totalCost.toFixed(4)}
          </p>
        </div>
      </div>

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

      {/* Loading skeleton */}
      {loading ? (
        <div className="space-y-3">
          {Array.from({ length: 9 }).map((_, i) => (
            <div key={i} className="h-20 bg-gray-800 rounded-lg animate-pulse" />
          ))}
        </div>
      ) : (
        <>
          {agents.length === 0 ? (
            <p className="text-gray-400 text-center py-12">No agents found.</p>
          ) : (
            <div className="space-y-2">
              {agents.map(renderCard)}
            </div>
          )}
        </>
      )}

      {/* Live Log slide panel */}
      {liveLogAgent && (
        <FlowLog
          agentType={liveLogAgent}
          open={true}
          onClose={() => setLiveLogAgent(null)}
        />
      )}
    </div>
  );

  function renderCard(s: (typeof agents)[number]) {
    const isTier = TIER_BADGE[s.agent_type];
    const style = STATUS_STYLE[s.status] ?? STATUS_STYLE.idle;

    return (
      <div
        key={s.agent_type}
        className="bg-gray-800 rounded-lg p-4 flex items-center justify-between hover:bg-gray-750 transition-colors"
      >
        <div className="flex-1 min-w-0">
          <div className="flex items-center gap-2">
            <h3 className="text-white font-medium capitalize truncate">
              {s.agent_type.replace(/_/g, " ")}
            </h3>
            {isTier && (
              <span className="text-[10px] bg-amber-500/20 text-amber-400 px-1.5 py-0.5 rounded font-medium">
                {isTier}
              </span>
            )}
            <span className={`inline-block px-2 py-0.5 rounded text-xs ${style}`}>
              {s.status}
            </span>
          </div>
          <p className="text-gray-400 text-sm truncate">{s.description}</p>
          <div className="flex items-center gap-4 mt-1.5 text-xs text-gray-500">
            <span>Today: <span className="text-white">{s.today.run_count} runs</span></span>
            {s.today.total_tokens > 0 && <span>{s.today.total_tokens} tokens</span>}
            {s.today.total_cost_usd > 0 && (
              <span className="text-amber-400">${s.today.total_cost_usd.toFixed(6)}</span>
            )}
            {s.last_run && (
              <span>
                Last: {new Date(s.last_run.started_at!).toLocaleTimeString()} ·{" "}
                {s.last_run.duration_secs?.toFixed(1) ?? "?"}s
              </span>
            )}
          </div>
        </div>

        <div className="flex items-center gap-2 ml-4">
          {s.last_run?.run_id && (
            <Link
              href={`/agents/runs?id=${s.last_run.run_id}`}
              className="px-3 py-2 bg-gray-700 hover:bg-gray-600 text-gray-300 text-xs rounded-md transition-colors"
            >
              Detail
            </Link>
          )}
          <button
            onClick={() => setLiveLogAgent(s.agent_type)}
            className="px-3 py-2 bg-gray-700 hover:bg-gray-600 text-emerald-400 text-xs rounded-md transition-colors"
          >
            ▶ Live Log
          </button>
          <button
            onClick={() => trigger(s.agent_type)}
            disabled={triggering === s.agent_type}
            className="px-4 py-2 bg-indigo-600 hover:bg-indigo-700 disabled:opacity-50 disabled:cursor-not-allowed text-white text-sm rounded-md transition-colors"
          >
            {triggering === s.agent_type ? "..." : "Run"}
          </button>
        </div>
      </div>
    );
  }
}
