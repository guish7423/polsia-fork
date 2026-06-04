"use client";

import { useCallback, useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import {
  api,
  listWorkflows,
  createWorkflow,
  deleteWorkflow,
  runWorkflow,
  type WorkflowDefinition,
} from "@/lib/api";
import { PageTitle } from "@/components/PageTitle";
import {
  Loader2,
  Plus,
  Play,
  Pencil,
  Trash2,
  X,
  AlertCircle,
  Workflow,
} from "lucide-react";

export default function WorkflowsPage() {
  const router = useRouter();
  const [workflows, setWorkflows] = useState<WorkflowDefinition[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  // Create form state
  const [showCreate, setShowCreate] = useState(false);
  const [newName, setNewName] = useState("");
  const [newDesc, setNewDesc] = useState("");
  const [creating, setCreating] = useState(false);

  // Action states
  const [runningId, setRunningId] = useState<number | null>(null);
  const [deletingId, setDeletingId] = useState<number | null>(null);
  const [runFeedback, setRunFeedback] = useState<{
    id: number;
    message: string;
  } | null>(null);

  const fetchWorkflows = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const data = await listWorkflows();
      setWorkflows(data.items ?? []);
    } catch (e) {
      setError(
        e instanceof Error ? e.message : "Failed to fetch workflows",
      );
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    fetchWorkflows();
  }, [fetchWorkflows]);

  async function handleCreate(e: React.FormEvent) {
    e.preventDefault();
    if (!newName.trim()) return;
    setCreating(true);
    try {
      await createWorkflow({ name: newName.trim(), description: newDesc.trim() });
      setNewName("");
      setNewDesc("");
      setShowCreate(false);
      await fetchWorkflows();
    } catch (err) {
      setError(
        err instanceof Error ? err.message : "Failed to create workflow",
      );
    } finally {
      setCreating(false);
    }
  }

  async function handleRun(id: number) {
    setRunningId(id);
    setRunFeedback(null);
    try {
      const result = await runWorkflow(id);
      const runId =
        (result as Record<string, unknown>)?.workflow_run_id ??
        (result as Record<string, unknown>)?.run_id ??
        "N/A";
      setRunFeedback({
        id,
        message: `Run started — ID: ${runId}`,
      });
    } catch (err) {
      setError(
        err instanceof Error
          ? err.message
          : `Failed to run workflow #${id}`,
      );
    } finally {
      setRunningId(null);
    }
  }

  async function handleDelete(id: number) {
    if (!window.confirm("Delete this workflow?")) return;
    setDeletingId(id);
    try {
      await deleteWorkflow(id);
      setWorkflows((prev) => prev.filter((w) => w.id !== id));
    } catch (err) {
      setError(
        err instanceof Error ? err.message : `Failed to delete workflow #${id}`,
      );
    } finally {
      setDeletingId(null);
    }
  }

  function formatDate(raw: string) {
    try {
      return new Date(raw).toLocaleDateString(undefined, {
        year: "numeric",
        month: "short",
        day: "numeric",
      });
    } catch {
      return raw;
    }
  }

  return (
    <div className="p-6 space-y-6">
      {/* Header */}
      <div className="flex items-center justify-between">
        <PageTitle i18nKey="workflow.title" />
        <button
          onClick={() => setShowCreate(!showCreate)}
          className="flex items-center gap-2 px-4 py-2 bg-indigo-600 hover:bg-indigo-500 text-white text-sm rounded-lg transition-colors"
        >
          <Plus size={16} />
          Create Workflow
        </button>
      </div>

      {/* Run feedback toast */}
      {runFeedback && (
        <div className="flex items-center gap-2 bg-green-900/30 border border-green-700 text-green-300 rounded-lg p-3 text-sm">
          <span>{runFeedback.message}</span>
          <button
            onClick={() => setRunFeedback(null)}
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

      {/* Create form */}
      {showCreate && (
        <form
          onSubmit={handleCreate}
          className="bg-gray-800 rounded-lg p-4 space-y-3 border border-gray-700"
        >
          <div>
            <label className="block text-xs text-gray-400 mb-1">Name</label>
            <input
              value={newName}
              onChange={(e) => setNewName(e.target.value)}
              placeholder="My workflow"
              required
              className="w-full bg-gray-700 text-white rounded px-3 py-2 text-sm placeholder-gray-500 focus:outline-none focus:ring-2 focus:ring-indigo-500"
            />
          </div>
          <div>
            <label className="block text-xs text-gray-400 mb-1">
              Description
            </label>
            <input
              value={newDesc}
              onChange={(e) => setNewDesc(e.target.value)}
              placeholder="What this workflow does"
              className="w-full bg-gray-700 text-white rounded px-3 py-2 text-sm placeholder-gray-500 focus:outline-none focus:ring-2 focus:ring-indigo-500"
            />
          </div>
          <div className="flex gap-2 pt-1">
            <button
              type="submit"
              disabled={creating || !newName.trim()}
              className="flex items-center gap-2 px-4 py-2 bg-indigo-600 hover:bg-indigo-500 disabled:opacity-50 text-white text-sm rounded-lg transition-colors"
            >
              {creating && <Loader2 size={14} className="animate-spin" />}
              Create
            </button>
            <button
              type="button"
              onClick={() => setShowCreate(false)}
              className="px-4 py-2 bg-gray-700 hover:bg-gray-600 text-gray-300 text-sm rounded-lg transition-colors"
            >
              Cancel
            </button>
          </div>
        </form>
      )}

      {/* Workflow list */}
      {loading ? (
        <div className="flex items-center justify-center py-12 text-gray-400">
          <Loader2 size={24} className="animate-spin mr-2" />
          Loading...
        </div>
      ) : workflows.length === 0 ? (
        <div className="text-center py-16 text-gray-400">
          <Workflow size={48} className="mx-auto mb-3 opacity-50" />
          <p className="text-lg font-medium text-gray-500">
            No workflows yet
          </p>
          <p className="text-sm mt-1">
            Create your first workflow to get started.
          </p>
        </div>
      ) : (
        <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
          {workflows.map((wf) => (
            <div
              key={wf.id}
              className="bg-gray-800 rounded-lg p-4 border border-gray-700 flex flex-col"
            >
              {/* Card header */}
              <div className="flex items-start justify-between mb-2">
                <h3 className="text-white font-semibold truncate">
                  {wf.name}
                </h3>
                <span
                  className={`text-xs px-2 py-0.5 rounded-full shrink-0 ml-2 ${
                    wf.is_active
                      ? "bg-green-900/50 text-green-400 border border-green-700"
                      : "bg-gray-700 text-gray-400 border border-gray-600"
                  }`}
                >
                  {wf.is_active ? "active" : "inactive"}
                </span>
              </div>

              {/* Description */}
              {wf.description && (
                <p className="text-gray-400 text-sm mb-2 line-clamp-2">
                  {wf.description}
                </p>
              )}

              {/* Meta row */}
              <div className="flex items-center gap-3 text-xs text-gray-500 mb-4">
                <span>{wf.nodes.length} node{wf.nodes.length !== 1 ? "s" : ""}</span>
                <span>{formatDate(wf.created_at)}</span>
              </div>

              {/* Actions */}
              <div className="flex gap-2 mt-auto">
                <button
                  onClick={() => router.push(`/workflows/${wf.id}`)}
                  className="flex items-center gap-1.5 px-3 py-1.5 bg-gray-700 hover:bg-gray-600 text-gray-200 text-xs rounded transition-colors"
                >
                  <Pencil size={12} />
                  Edit
                </button>
                <button
                  onClick={() => handleRun(wf.id)}
                  disabled={runningId === wf.id}
                  className="flex items-center gap-1.5 px-3 py-1.5 bg-blue-600 hover:bg-blue-500 disabled:opacity-50 text-white text-xs rounded transition-colors"
                >
                  {runningId === wf.id ? (
                    <Loader2 size={12} className="animate-spin" />
                  ) : (
                    <Play size={12} />
                  )}
                  Run
                </button>
                <button
                  onClick={() => handleDelete(wf.id)}
                  disabled={deletingId === wf.id}
                  className="flex items-center gap-1.5 px-3 py-1.5 bg-red-700 hover:bg-red-600 disabled:opacity-50 text-white text-xs rounded transition-colors ml-auto"
                >
                  {deletingId === wf.id ? (
                    <Loader2 size={12} className="animate-spin" />
                  ) : (
                    <Trash2 size={12} />
                  )}
                  Delete
                </button>
              </div>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}
