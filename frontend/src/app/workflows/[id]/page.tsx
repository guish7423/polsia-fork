"use client";

import { useCallback, useEffect, useRef, useState } from "react";
import { useParams, useRouter } from "next/navigation";
import {
  api,
  getWorkflow,
  runWorkflow,
  type WorkflowDefinition,
  type WorkflowRun,
  type WorkflowNode,
  type WorkflowEdge,
} from "@/lib/api";
import { PageTitle } from "@/components/PageTitle";
import { WorkflowCanvas } from "@/components/workflow/WorkflowCanvas";
import { NodeConfigPanel } from "@/components/workflow/NodeConfigPanel";
import {
  Loader2,
  Play,
  ArrowLeft,
  ChevronDown,
  ChevronRight,
  AlertCircle,
  X,
  CheckCircle,
  Clock,
  XCircle,
  RefreshCw,
  Eye,
  Pencil,
} from "lucide-react";

const STATUS_ICON: Record<string, typeof Clock> = {
  pending: Clock,
  running: RefreshCw,
  completed: CheckCircle,
  failed: XCircle,
};

const STATUS_COLOR: Record<string, string> = {
  pending: "text-yellow-400",
  running: "text-blue-400",
  completed: "text-green-400",
  failed: "text-red-400",
};

export default function WorkflowDetailPage() {
  const params = useParams();
  const router = useRouter();
  const id = Number(params.id);

  const [workflow, setWorkflow] = useState<WorkflowDefinition | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  // Edit mode
  const [editing, setEditing] = useState(false);
  const [editNodes, setEditNodes] = useState<WorkflowNode[]>([]);
  const [editEdges, setEditEdges] = useState<WorkflowEdge[]>([]);
  const [saving, setSaving] = useState(false);
  const [selectedNodeId, setSelectedNodeId] = useState<string | null>(null);
  const hasUnsavedRef = useRef(false);

  // Run state
  const [running, setRunning] = useState(false);
  const [runResult, setRunResult] = useState<{
    runId: number;
    status: string;
  } | null>(null);

  // Runs table
  const [runs, setRuns] = useState<WorkflowRun[]>([]);
  const [runsLoading, setRunsLoading] = useState(false);
  const [expandedRunId, setExpandedRunId] = useState<number | null>(null);

  const fetchWorkflow = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const data = await getWorkflow(id);
      setWorkflow(data);
    } catch (e) {
      setError(
        e instanceof Error ? e.message : `Failed to load workflow #${id}`,
      );
    } finally {
      setLoading(false);
    }
  }, [id]);

  const fetchRuns = useCallback(async () => {
    setRunsLoading(true);
    try {
      const data = await api.get<{ items: WorkflowRun[]; total: number }>(
        `/workflows/${id}/runs`,
      );
      setRuns(data.items ?? []);
    } catch {
      // Runs endpoint may not exist yet — silently degrade
      setRuns([]);
    } finally {
      setRunsLoading(false);
    }
  }, [id]);

  useEffect(() => {
    fetchWorkflow();
    fetchRuns();
  }, [fetchWorkflow, fetchRuns]);

  function handleEditToggle() {
    if (editing) {
      // Switching to view mode — discard unsaved changes
      setEditing(false);
      setSelectedNodeId(null);
      hasUnsavedRef.current = false;
    } else {
      // Switching to edit mode — snapshot current nodes/edges
      setEditNodes(workflow?.nodes ?? []);
      setEditEdges(workflow?.edges ?? []);
      setEditing(true);
    }
  }

  async function handleSave(nodes: WorkflowNode[], edges: WorkflowEdge[]) {
    setSaving(true);
    try {
      await api.put(`/workflows/${id}`, { nodes, edges });
      // Refresh workflow data
      const data = await getWorkflow(id);
      setWorkflow(data);
      setEditing(false);
      setSelectedNodeId(null);
      hasUnsavedRef.current = false;
    } catch (e) {
      setError(
        e instanceof Error ? e.message : "Failed to save workflow",
      );
    } finally {
      setSaving(false);
    }
  }

  function handleCanvasSave(nodes: WorkflowNode[], edges: WorkflowEdge[]) {
    setEditNodes(nodes);
    setEditEdges(edges);
    hasUnsavedRef.current = true;
  }

  // ── Beforeunload warning for unsaved changes ────────────────────────────

  useEffect(() => {
    if (!editing || !hasUnsavedRef.current) return;
    const handler = (e: BeforeUnloadEvent) => {
      e.preventDefault();
    };
    window.addEventListener("beforeunload", handler);
    return () => window.removeEventListener("beforeunload", handler);
  }, [editing]);

  async function handleRun() {
    setRunning(true);
    setRunResult(null);
    try {
      const result = await runWorkflow(id);
      const rid =
        (result as Record<string, unknown>)?.workflow_run_id ??
        (result as Record<string, unknown>)?.run_id;
      setRunResult({
        runId: Number(rid) ?? 0,
        status: (result as Record<string, unknown>)?.status as string ?? "running",
      });
      // Refresh runs after a short delay
      setTimeout(() => fetchRuns(), 1000);
    } catch (e) {
      setError(
        e instanceof Error ? e.message : `Failed to run workflow #${id}`,
      );
    } finally {
      setRunning(false);
    }
  }

  function StatusBadge({ status }: { status: string }) {
    const Icon = STATUS_ICON[status] ?? Clock;
    return (
      <span
        className={`inline-flex items-center gap-1 text-xs font-medium ${STATUS_COLOR[status] ?? "text-gray-400"}`}
      >
        <Icon size={14} className={status === "running" ? "animate-spin" : ""} />
        {status}
      </span>
    );
  }

  if (loading) {
    return (
      <div className="flex items-center justify-center h-64">
        <Loader2 size={32} className="animate-spin text-indigo-500" />
      </div>
    );
  }

  if (error && !workflow) {
    return (
      <div className="p-6 space-y-4">
        <button
          onClick={() => router.push("/workflows")}
          className="flex items-center gap-1 text-sm text-gray-400 hover:text-white transition-colors"
        >
          <ArrowLeft size={16} />
          Back to workflows
        </button>
        <div className="flex items-center gap-2 bg-red-900/30 border border-red-700 text-red-300 rounded-lg p-4 text-sm">
          <AlertCircle size={18} />
          <span>{error}</span>
        </div>
      </div>
    );
  }

  if (!workflow) return null;

  return (
    <div className="p-6 space-y-6">
      {/* Back nav */}
      <button
        onClick={() => router.push("/workflows")}
        className="flex items-center gap-1 text-sm text-gray-400 hover:text-white transition-colors"
      >
        <ArrowLeft size={16} />
        Back to workflows
      </button>

      {/* Header */}
      <div className="flex items-start justify-between gap-4">
        <div className="min-w-0">
          <PageTitle i18nKey="workflow.title" fallback={workflow.name} />
          {workflow.description && (
            <p className="text-gray-400 text-sm mt-1">
              {workflow.description}
            </p>
          )}
          <div className="flex items-center gap-3 text-xs text-gray-500 mt-2">
            <span>
              {workflow.nodes.length} node{workflow.nodes.length !== 1 ? "s" : ""}
              {" · "}
              {workflow.edges.length} edge{workflow.edges.length !== 1 ? "s" : ""}
            </span>
            <span>
              Updated {new Date(workflow.updated_at).toLocaleDateString()}
            </span>
          </div>
        </div>
        <div className="flex items-center gap-2 shrink-0">
          {/* Edit/View toggle */}
          <button
            onClick={handleEditToggle}
            className={`flex items-center gap-1.5 px-3 py-2 text-xs font-medium rounded-lg transition-colors ${
              editing
                ? "bg-indigo-600 text-white hover:bg-indigo-500"
                : "bg-gray-700 text-gray-300 hover:bg-gray-600"
            }`}
          >
            {editing ? <Eye size={14} /> : <Pencil size={14} />}
            {editing ? "View" : "Edit"}
          </button>
          <button
            onClick={handleRun}
            disabled={running || editing}
            className="flex items-center gap-2 px-5 py-2.5 bg-indigo-600 hover:bg-indigo-500 disabled:opacity-50 text-white text-sm font-medium rounded-lg transition-colors"
          >
            {running ? (
              <Loader2 size={16} className="animate-spin" />
            ) : (
              <Play size={16} />
            )}
            {running ? "Running…" : "Run Workflow"}
          </button>
        </div>
      </div>

      {/* Run result banner */}
      {runResult && (
        <div className="flex items-center gap-2 bg-green-900/30 border border-green-700 text-green-300 rounded-lg p-3 text-sm">
          <CheckCircle size={16} />
          <span>
            Run triggered — ID: {runResult.runId} · Status: {runResult.status}
          </span>
          <button
            onClick={() => setRunResult(null)}
            className="ml-auto text-green-400 hover:text-green-200"
          >
            <X size={16} />
          </button>
        </div>
      )}

      {/* Error banner */}
      {error && (
        <div className="flex items-center gap-2 bg-red-900/30 border border-red-700 text-red-300 rounded-lg p-3 text-sm">
          <AlertCircle size={16} />
          <span>{error}</span>
          <button onClick={() => setError(null)} className="ml-auto">
            <X size={16} />
          </button>
        </div>
      )}

      {/* Workflow Canvas + Node Config */}
      <div className="flex gap-4">
        <div className="flex-1 bg-gray-900 rounded-lg border border-gray-700 overflow-hidden">
          <div className="p-3 border-b border-gray-700 bg-gray-800/50 flex items-center justify-between">
            <h3 className="text-sm font-medium text-gray-300">
              Workflow Canvas
            </h3>
            {editing && (
              <span className="text-xs text-indigo-400 font-medium bg-indigo-900/30 px-2 py-0.5 rounded">
                Editing mode
              </span>
            )}
          </div>
          <div className="h-[450px]">
            {(editing ? editNodes : workflow.nodes).length > 0 || editing ? (
              <WorkflowCanvas
                key={editing ? "edit" : "view"}
                initialNodes={editing ? editNodes : workflow.nodes}
                initialEdges={editing ? editEdges : workflow.edges}
                readOnly={!editing}
                onSave={editing ? handleCanvasSave : undefined}
                onNodeSelect={setSelectedNodeId}
              />
            ) : (
              <div className="flex items-center justify-center h-full text-gray-500 text-sm">
                No nodes in this workflow yet
              </div>
            )}
          </div>
        </div>

        {/* Node config panel — visible when a node is selected */}
        {selectedNodeId && editing && (
          <NodeConfigPanel
            nodeId={selectedNodeId}
            nodes={editNodes}
            edges={editEdges}
            onUpdateNode={(id, data) => {
              setEditNodes((prev) =>
                prev.map((n) =>
                  n.id === id ? { ...n, data: { ...n.data, ...data } } : n,
                ),
              );
            }}
            onClose={() => setSelectedNodeId(null)}
          />
        )}
      </div>

      {/* Save bar — visible in edit mode */}
      {editing && (
        <div className="flex items-center justify-end gap-3 px-4 py-3 bg-gray-900 rounded-lg border border-gray-700">
          <span className="text-xs text-gray-500">
            {hasUnsavedRef.current
              ? "Unsaved changes"
              : "No unsaved changes"}
          </span>
          <button
            onClick={() => handleSave(editNodes, editEdges)}
            disabled={saving || !hasUnsavedRef.current}
            className="px-4 py-1.5 bg-indigo-600 hover:bg-indigo-500 disabled:opacity-50 text-white text-xs font-medium rounded-md transition-colors"
          >
            {saving ? (
              <Loader2 size={14} className="animate-spin" />
            ) : (
              "Save Changes"
            )}
          </button>
        </div>
      )}

      {/* Runs section */}
      <div className="bg-gray-900 rounded-lg border border-gray-700 overflow-hidden">
        <div className="p-3 border-b border-gray-700 bg-gray-800/50 flex items-center justify-between">
          <h3 className="text-sm font-medium text-gray-300">Run History</h3>
          <button
            onClick={fetchRuns}
            disabled={runsLoading}
            className="text-xs text-gray-400 hover:text-white transition-colors"
          >
            {runsLoading ? "Refreshing…" : "Refresh"}
          </button>
        </div>

        {runsLoading && runs.length === 0 ? (
          <div className="flex items-center justify-center py-8 text-gray-500">
            <Loader2 size={18} className="animate-spin mr-2" />
            Loading runs…
          </div>
        ) : runs.length === 0 ? (
          <div className="text-center py-8 text-gray-500 text-sm">
            No runs yet. Click "Run Workflow" to start one.
          </div>
        ) : (
          <div className="divide-y divide-gray-700">
            {runs.map((run) => {
              const isExpanded = expandedRunId === run.id;
              return (
                <div key={run.id}>
                  {/* Run row */}
                  <button
                    onClick={() =>
                      setExpandedRunId(isExpanded ? null : run.id)
                    }
                    className="w-full flex items-center gap-3 px-4 py-3 text-left hover:bg-gray-800/50 transition-colors"
                  >
                    {isExpanded ? (
                      <ChevronDown size={14} className="text-gray-500 shrink-0" />
                    ) : (
                      <ChevronRight size={14} className="text-gray-500 shrink-0" />
                    )}
                    <span className="text-xs text-gray-500 font-mono w-20 shrink-0">
                      #{run.id}
                    </span>
                    <StatusBadge status={run.status} />
                    {run.started_at && (
                      <span className="text-xs text-gray-500 ml-auto">
                        {new Date(run.started_at).toLocaleString()}
                      </span>
                    )}
                  </button>

                  {/* Expanded details */}
                  {isExpanded && (
                    <div className="px-4 pb-3 pt-0">
                      <div className="bg-gray-800 rounded p-3 space-y-2 text-xs font-mono">
                        <div>
                          <span className="text-gray-500">Run ID: </span>
                          <span className="text-gray-300">{run.id}</span>
                        </div>
                        <div>
                          <span className="text-gray-500">Status: </span>
                          <StatusBadge status={run.status} />
                        </div>
                        {run.started_at && (
                          <div>
                            <span className="text-gray-500">Started: </span>
                            <span className="text-gray-300">
                              {new Date(run.started_at).toLocaleString()}
                            </span>
                          </div>
                        )}
                        {run.completed_at && (
                          <div>
                            <span className="text-gray-500">Completed: </span>
                            <span className="text-gray-300">
                              {new Date(run.completed_at).toLocaleString()}
                            </span>
                          </div>
                        )}
                        {run.error && (
                          <div>
                            <span className="text-gray-500">Error: </span>
                            <span className="text-red-400">{run.error}</span>
                          </div>
                        )}
                        {run.node_states &&
                          Object.keys(run.node_states).length > 0 && (
                            <div>
                              <span className="text-gray-500 block mb-1">
                                Node States:
                              </span>
                              <pre className="text-gray-400 whitespace-pre-wrap bg-gray-900 rounded p-2 max-h-40 overflow-auto">
                                {JSON.stringify(run.node_states, null, 2)}
                              </pre>
                            </div>
                          )}
                      </div>
                    </div>
                  )}
                </div>
              );
            })}
          </div>
        )}
      </div>
    </div>
  );
}
