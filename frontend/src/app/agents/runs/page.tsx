"use client";
import { useCallback, useEffect, useState } from "react";
import Link from "next/link";
import { api, type AgentRunSummary, type AgentRunDetail } from "@/lib/api";
import { PageTitle } from "@/components/PageTitle";

const STATUS_BADGE: Record<string, string> = {
  completed: "bg-green-500/20 text-green-400",
  running: "bg-blue-500/20 text-blue-400 animate-pulse",
  error: "bg-red-500/20 text-red-400",
  interrupt: "bg-yellow-500/20 text-yellow-400",
  pending: "bg-gray-600/40 text-gray-300",
};

const RUNS_PER_PAGE = 20;

export default function AgentRunsPage() {
  const [runs, setRuns] = useState<AgentRunSummary[]>([]);
  const [total, setTotal] = useState(0);
  const [offset, setOffset] = useState(0);
  const [loading, setLoading] = useState(true);
  const [filterAgent, setFilterAgent] = useState("");
  const [filterStatus, setFilterStatus] = useState("");
  const [selectedRun, setSelectedRun] = useState<AgentRunDetail | null>(null);

  const fetchRuns = useCallback(async (o: number) => {
    setLoading(true);
    try {
      let path = `/agents/runs?limit=${RUNS_PER_PAGE}&offset=${o}`;
      if (filterAgent) path += `&agent_type=${filterAgent}`;
      if (filterStatus) path += `&status=${filterStatus}`;
      const data = await api.get<{
        total: number;
        limit: number;
        offset: number;
        runs: AgentRunSummary[];
      }>(path);
      setRuns(data.runs);
      setTotal(data.total);
    } catch (e) {
      console.error("Failed to load runs:", e);
    } finally {
      setLoading(false);
    }
  }, [filterAgent, filterStatus]);

  useEffect(() => {
    fetchRuns(offset);
  }, [offset, fetchRuns]);

  const fetchDetail = async (runId: number) => {
    try {
      const data = await api.get<AgentRunDetail>(`/agents/runs/${runId}`);
      setSelectedRun(data);
    } catch (e) {
      console.error("Failed to load run detail:", e);
    }
  };

  const totalPages = Math.ceil(total / RUNS_PER_PAGE);
  const currentPage = Math.floor(offset / RUNS_PER_PAGE) + 1;

  return (
    <div className="p-6 space-y-6">
      <div className="flex items-center justify-between">
        <PageTitle i18nKey="Agent Run History" />
        <Link
          href="/agents"
          className="text-indigo-400 hover:text-indigo-300 text-sm transition-colors"
        >
          ← Agents
        </Link>
      </div>

      {/* Filters */}
      <div className="flex items-center gap-3">
        <input
          placeholder="Filter by agent type..."
          value={filterAgent}
          onChange={(e) => { setFilterAgent(e.target.value); setOffset(0); }}
          className="bg-gray-800 border border-gray-700 rounded-md px-3 py-1.5 text-sm text-white placeholder-gray-500"
        />
        <select
          value={filterStatus}
          onChange={(e) => { setFilterStatus(e.target.value); setOffset(0); }}
          className="bg-gray-800 border border-gray-700 rounded-md px-3 py-1.5 text-sm text-white"
        >
          <option value="">All status</option>
          <option value="completed">Completed</option>
          <option value="running">Running</option>
          <option value="error">Error</option>
          <option value="interrupt">Interrupt</option>
        </select>
        <span className="text-gray-500 text-sm ml-auto">
          {total} runs total
        </span>
      </div>

      {/* Runs table */}
      {loading ? (
        <div className="space-y-2">
          {Array.from({ length: 8 }).map((_, i) => (
            <div key={i} className="h-12 bg-gray-800 rounded-lg animate-pulse" />
          ))}
        </div>
      ) : runs.length === 0 ? (
        <div className="text-center py-12 text-gray-500">
          No agent runs found.
        </div>
      ) : (
        <div className="bg-gray-800 rounded-lg overflow-hidden">
          <table className="w-full text-sm">
            <thead>
              <tr className="border-b border-gray-700 text-gray-400 text-xs uppercase tracking-wider">
                <th className="text-left p-3">ID</th>
                <th className="text-left p-3">Agent</th>
                <th className="text-left p-3">Status</th>
                <th className="text-right p-3">Duration</th>
                <th className="text-right p-3">Tokens</th>
                <th className="text-right p-3">Cost</th>
                <th className="text-right p-3">LLM Calls</th>
                <th className="text-left p-3">Started</th>
                <th className="p-3"></th>
              </tr>
            </thead>
            <tbody>
              {runs.map((run) => (
                <tr key={run.id} className="border-b border-gray-700/50 hover:bg-gray-750">
                  <td className="p-3 text-gray-400 font-mono text-xs">#{run.id}</td>
                  <td className="p-3 text-white capitalize">
                    {run.agent_type.replace(/_/g, " ")}
                  </td>
                  <td className="p-3">
                    <span className={`inline-block px-2 py-0.5 rounded text-xs ${STATUS_BADGE[run.status] ?? "bg-gray-600/40 text-gray-300"}`}>
                      {run.status}
                    </span>
                  </td>
                  <td className="p-3 text-right text-gray-300 font-mono text-xs">
                    {run.duration_secs != null ? `${run.duration_secs.toFixed(1)}s` : "-"}
                  </td>
                  <td className="p-3 text-right text-gray-300 font-mono text-xs">
                    {run.tokens_used ?? "-"}
                  </td>
                  <td className="p-3 text-right text-amber-400 font-mono text-xs">
                    {run.cost_usd != null ? `$${run.cost_usd.toFixed(6)}` : "-"}
                  </td>
                  <td className="p-3 text-right text-gray-300 font-mono text-xs">
                    {run.llm_call_count ?? "-"}
                  </td>
                  <td className="p-3 text-gray-500 text-xs">
                    {run.started_at ? new Date(run.started_at).toLocaleString() : "-"}
                  </td>
                  <td className="p-3">
                    <button
                      onClick={() => fetchDetail(run.id)}
                      className="text-indigo-400 hover:text-indigo-300 text-xs transition-colors"
                    >
                      Detail
                    </button>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}

      {/* Pagination */}
      {totalPages > 1 && (
        <div className="flex items-center justify-center gap-2 text-sm">
          <button
            onClick={() => setOffset(Math.max(0, offset - RUNS_PER_PAGE))}
            disabled={offset === 0}
            className="px-3 py-1 bg-gray-800 hover:bg-gray-700 disabled:opacity-50 rounded-md text-gray-300"
          >
            ← Prev
          </button>
          <span className="text-gray-500">
            Page {currentPage} of {totalPages}
          </span>
          <button
            onClick={() => setOffset(offset + RUNS_PER_PAGE)}
            disabled={offset + RUNS_PER_PAGE >= total}
            className="px-3 py-1 bg-gray-800 hover:bg-gray-700 disabled:opacity-50 rounded-md text-gray-300"
          >
            Next →
          </button>
        </div>
      )}

      {/* Detail modal */}
      {selectedRun && (
        <div
          className="fixed inset-0 bg-black/60 flex items-center justify-center z-50 p-4"
          onClick={() => setSelectedRun(null)}
        >
          <div
            className="bg-gray-800 rounded-xl max-w-2xl w-full max-h-[80vh] overflow-y-auto p-6 space-y-4"
            onClick={(e) => e.stopPropagation()}
          >
            <div className="flex items-center justify-between">
              <h2 className="text-white text-lg font-semibold">
                Run #{selectedRun.id} — {selectedRun.agent_type.replace(/_/g, " ")}
              </h2>
              <button
                onClick={() => setSelectedRun(null)}
                className="text-gray-400 hover:text-white text-xl"
              >
                ✕
              </button>
            </div>

            {/* Status */}
            <div className="flex items-center gap-3 text-sm">
              <span className={`px-2 py-0.5 rounded text-xs ${STATUS_BADGE[selectedRun.status] ?? ""}`}>
                {selectedRun.status}
              </span>
              <span className="text-gray-400">
                Started: {selectedRun.started_at ? new Date(selectedRun.started_at).toLocaleString() : "-"}
              </span>
              {selectedRun.ended_at && (
                <span className="text-gray-400">
                  Ended: {new Date(selectedRun.ended_at).toLocaleString()}
                </span>
              )}
            </div>

            {/* Telemetry */}
            <div className="grid grid-cols-4 gap-3">
              {[
                { label: "Duration", value: selectedRun.telemetry.duration_secs != null ? `${selectedRun.telemetry.duration_secs.toFixed(1)}s` : "-" },
                { label: "Tokens", value: selectedRun.telemetry.tokens_used ?? "-" },
                { label: "Cost", value: selectedRun.telemetry.cost_usd != null ? `$${selectedRun.telemetry.cost_usd.toFixed(6)}` : "-" },
                { label: "LLM Calls", value: selectedRun.telemetry.llm_call_count ?? "-" },
              ].map((m) => (
                <div key={m.label} className="bg-gray-900 rounded-lg p-3 text-center">
                  <p className="text-gray-500 text-xs">{m.label}</p>
                  <p className="text-white text-sm font-mono mt-1">{m.value}</p>
                </div>
              ))}
            </div>

            {/* LLM Calls */}
            {selectedRun.llm_calls.length > 0 && (
              <div>
                <h3 className="text-gray-400 text-sm font-medium mb-2">LLM Calls</h3>
                <div className="space-y-1">
                  {selectedRun.llm_calls.map((call) => (
                    <div key={call.id} className="bg-gray-900 rounded-md px-3 py-2 flex items-center justify-between text-xs">
                      <span className="text-gray-300">{call.model}</span>
                      <span className="text-gray-500">
                        {call.input_tokens}→{call.output_tokens} tokens
                      </span>
                      <span className="text-amber-400">${call.cost_usd.toFixed(6)}</span>
                      <span className="text-gray-500">{call.duration_ms}ms</span>
                      <span className={call.success ? "text-green-400" : "text-red-400"}>
                        {call.success ? "OK" : "FAIL"}
                      </span>
                    </div>
                  ))}
                </div>
              </div>
            )}

            {/* Execution spans */}
            {selectedRun.execution_spans && (
              <div>
                <h3 className="text-gray-400 text-sm font-medium mb-2">Execution Timeline</h3>
                <div className="space-y-1">
                  {(selectedRun.execution_spans as any).spans?.map((span: any, i: number) => (
                    <div key={i} className="flex items-center gap-3 text-xs text-gray-400">
                      <span className="text-gray-500 w-16">{span.span_type}</span>
                      <span className="text-gray-600">{span.started_at?.split("T")[1]?.split("Z")[0]}</span>
                      <span className="text-gray-500">{span.duration_ms}ms</span>
                      <span className="truncate">
                        {span.detail?.to ? `→ ${span.detail.to}` : span.detail?.error ? `❌ ${span.detail.error}` : ""}
                      </span>
                    </div>
                  ))}
                </div>
              </div>
            )}

            {/* Output preview */}
            {selectedRun.output && (
              <div>
                <h3 className="text-gray-400 text-sm font-medium mb-2">Output</h3>
                <pre className="bg-gray-900 rounded-md p-3 text-xs text-gray-300 overflow-x-auto max-h-40">
                  {JSON.stringify(selectedRun.output, null, 2).slice(0, 2000)}
                </pre>
              </div>
            )}
          </div>
        </div>
      )}
    </div>
  );
}
