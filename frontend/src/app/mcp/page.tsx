"use client";

import { useCallback, useEffect, useState } from "react";
import { api, type MCPTool } from "@/lib/api";
import { PageTitle, Text } from "@/components/PageTitle";
import { Loader2, Plus, Trash2, Play, X, CheckCircle, AlertCircle } from "lucide-react";

async function apiDelete(path: string) {
  const API_URL = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8001";
  const API_KEY = process.env.NEXT_PUBLIC_API_KEY ?? "";
  const res = await fetch(`${API_URL}/api/v1${path}`, {
    method: "DELETE",
    headers: {
      "Content-Type": "application/json",
      "X-API-Key": API_KEY,
    },
  });
  if (!res.ok) {
    const detail = await res.text().catch(() => res.statusText);
    throw new Error(`API ${res.status}: ${detail}`);
  }
  return res.json();
}

export default function McpPage() {
  const [tools, setTools] = useState<MCPTool[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  // Register form state
  const [showRegister, setShowRegister] = useState(false);
  const [regName, setRegName] = useState("");
  const [regDesc, setRegDesc] = useState("");
  const [regEndpoint, setRegEndpoint] = useState("");
  const [regSubmitting, setRegSubmitting] = useState(false);

  // Execute state
  const [executingId, setExecutingId] = useState<number | null>(null);
  const [execResult, setExecResult] = useState<{ toolId: number; output: string } | null>(null);

  // Delete state
  const [deletingId, setDeletingId] = useState<number | null>(null);

  const fetchTools = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const data = await api.get<MCPTool[]>("/mcp/tools");
      setTools(data);
    } catch (e) {
      setError(e instanceof Error ? e.message : "Failed to fetch tools");
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    fetchTools();
  }, [fetchTools]);

  async function handleRegister(e: React.FormEvent) {
    e.preventDefault();
    if (!regName.trim() || !regEndpoint.trim()) return;
    setRegSubmitting(true);
    try {
      await api.post<MCPTool>("/mcp/tools", {
        name: regName.trim(),
        description: regDesc.trim(),
        endpoint: regEndpoint.trim(),
      });
      setRegName("");
      setRegDesc("");
      setRegEndpoint("");
      setShowRegister(false);
      await fetchTools();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Registration failed");
    } finally {
      setRegSubmitting(false);
    }
  }

  async function handleExecute(tool: MCPTool) {
    setExecutingId(tool.id);
    setExecResult(null);
    try {
      const result = await api.post<{ output: string }>(
        `/mcp/tools/${tool.id}/execute`,
        { params: {} }
      );
      setExecResult({
        toolId: tool.id,
        output: typeof result === "string" ? result : JSON.stringify(result, null, 2),
      });
    } catch (err) {
      setExecResult({
        toolId: tool.id,
        output: `Error: ${err instanceof Error ? err.message : "Execution failed"}`,
      });
    } finally {
      setExecutingId(null);
    }
  }

  async function handleDelete(toolId: number) {
    setDeletingId(toolId);
    try {
      await apiDelete(`/mcp/tools/${toolId}`);
      setTools((prev) => prev.filter((t) => t.id !== toolId));
    } catch (err) {
      setError(err instanceof Error ? err.message : "Delete failed");
    } finally {
      setDeletingId(null);
    }
  }

  return (
    <div className="p-6 space-y-6">
      {/* Header */}
      <div className="flex items-center justify-between">
        <PageTitle i18nKey="mcp.title" />
        <button
          onClick={() => setShowRegister(!showRegister)}
          className="flex items-center gap-2 px-4 py-2 bg-indigo-600 hover:bg-indigo-500 text-white text-sm rounded-lg transition-colors"
        >
          <Plus size={16} />
          <Text i18nKey="mcp.register" />
        </button>
      </div>

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

      {/* Register form */}
      {showRegister && (
        <form
          onSubmit={handleRegister}
          className="bg-gray-800 rounded-lg p-4 space-y-3 border border-gray-700"
        >
          <div>
            <label className="block text-xs text-gray-400 mb-1">Name</label>
            <input
              value={regName}
              onChange={(e) => setRegName(e.target.value)}
              placeholder="my-tool"
              required
              className="w-full bg-gray-700 text-white rounded px-3 py-2 text-sm placeholder-gray-500 focus:outline-none focus:ring-2 focus:ring-indigo-500"
            />
          </div>
          <div>
            <label className="block text-xs text-gray-400 mb-1">Description</label>
            <input
              value={regDesc}
              onChange={(e) => setRegDesc(e.target.value)}
              placeholder="What this tool does"
              className="w-full bg-gray-700 text-white rounded px-3 py-2 text-sm placeholder-gray-500 focus:outline-none focus:ring-2 focus:ring-indigo-500"
            />
          </div>
          <div>
            <label className="block text-xs text-gray-400 mb-1">Endpoint URL</label>
            <input
              value={regEndpoint}
              onChange={(e) => setRegEndpoint(e.target.value)}
              placeholder="https://api.example.com/tool"
              required
              className="w-full bg-gray-700 text-white rounded px-3 py-2 text-sm placeholder-gray-500 focus:outline-none focus:ring-2 focus:ring-indigo-500"
            />
          </div>
          <div className="flex gap-2 pt-1">
            <button
              type="submit"
              disabled={regSubmitting}
              className="flex items-center gap-2 px-4 py-2 bg-indigo-600 hover:bg-indigo-500 disabled:opacity-50 text-white text-sm rounded-lg transition-colors"
            >
              {regSubmitting && <Loader2 size={14} className="animate-spin" />}
              Submit
            </button>
            <button
              type="button"
              onClick={() => setShowRegister(false)}
              className="px-4 py-2 bg-gray-700 hover:bg-gray-600 text-gray-300 text-sm rounded-lg transition-colors"
            >
              Cancel
            </button>
          </div>
        </form>
      )}

      {/* Tool list */}
      {loading ? (
        <div className="flex items-center justify-center py-12 text-gray-400">
          <Loader2 size={24} className="animate-spin mr-2" />
          Loading...
        </div>
      ) : tools.length === 0 ? (
        <div className="text-center py-12 text-gray-400">
          <p><Text i18nKey="mcp.empty" /></p>
        </div>
      ) : (
        <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
          {tools.map((tool) => (
            <div key={tool.id} className="bg-gray-800 rounded-lg p-4 border border-gray-700 flex flex-col">
              {/* Card header */}
              <div className="flex items-start justify-between mb-2">
                <h3 className="text-white font-semibold truncate">{tool.name}</h3>
                <span
                  className={`text-xs px-2 py-0.5 rounded-full shrink-0 ml-2 ${
                    tool.enabled
                      ? "bg-green-900/50 text-green-400 border border-green-700"
                      : "bg-gray-700 text-gray-400 border border-gray-600"
                  }`}
                >
                  {tool.enabled ? "enabled" : "disabled"}
                </span>
              </div>

              {/* Description */}
              {tool.description && (
                <p className="text-gray-400 text-sm mb-2 line-clamp-2">{tool.description}</p>
              )}

              {/* Endpoint */}
              <p className="text-gray-500 text-xs mb-4 truncate font-mono" title={tool.endpoint}>
                {tool.endpoint}
              </p>

              {/* Actions */}
              <div className="flex gap-2 mt-auto">
                <button
                  onClick={() => handleExecute(tool)}
                  disabled={executingId === tool.id}
                  className="flex items-center gap-1.5 px-3 py-1.5 bg-blue-600 hover:bg-blue-500 disabled:opacity-50 text-white text-xs rounded transition-colors"
                >
                  {executingId === tool.id ? (
                    <Loader2 size={12} className="animate-spin" />
                  ) : (
                    <Play size={12} />
                  )}
                  <Text i18nKey="mcp.execute" />
                </button>
                <button
                  onClick={() => {
                    if (window.confirm("Delete this tool?")) handleDelete(tool.id);
                  }}
                  disabled={deletingId === tool.id}
                  className="flex items-center gap-1.5 px-3 py-1.5 bg-red-700 hover:bg-red-600 disabled:opacity-50 text-white text-xs rounded transition-colors"
                >
                  {deletingId === tool.id ? (
                    <Loader2 size={12} className="animate-spin" />
                  ) : (
                    <Trash2 size={12} />
                  )}
                  <Text i18nKey="mcp.delete" />
                </button>
              </div>
            </div>
          ))}
        </div>
      )}

      {/* Execution result modal */}
      {execResult && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/60">
          <div className="bg-gray-800 rounded-lg border border-gray-700 w-full max-w-lg mx-4 max-h-[80vh] flex flex-col">
            <div className="flex items-center justify-between p-4 border-b border-gray-700">
              <h3 className="text-white font-semibold flex items-center gap-2">
                <CheckCircle size={18} className="text-blue-400" />
                Execution Result
              </h3>
              <button onClick={() => setExecResult(null)} className="text-gray-400 hover:text-white">
                <X size={18} />
              </button>
            </div>
            <pre className="p-4 text-sm text-gray-200 overflow-auto whitespace-pre-wrap break-all font-mono">
              {execResult.output}
            </pre>
            <div className="p-3 border-t border-gray-700 flex justify-end">
              <button
                onClick={() => setExecResult(null)}
                className="px-4 py-2 bg-gray-700 hover:bg-gray-600 text-white text-sm rounded transition-colors"
              >
                Close
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
