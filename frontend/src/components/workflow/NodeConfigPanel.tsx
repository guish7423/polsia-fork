"use client";

import { useState } from "react";
import type { WorkflowNode, WorkflowEdge } from "@/lib/api";
import { X, Bot, Wrench, Zap, Check } from "lucide-react";

const NODE_ICONS: Record<string, typeof Bot> = {
  agent: Bot,
  tool: Wrench,
  trigger: Zap,
  output: Check,
};

const NODE_COLORS: Record<string, string> = {
  agent: "text-indigo-400 bg-indigo-900/30",
  tool: "text-emerald-400 bg-emerald-900/30",
  trigger: "text-amber-400 bg-amber-900/30",
  output: "text-gray-400 bg-gray-800/50",
};

export interface NodeConfigPanelProps {
  nodeId: string;
  nodes: WorkflowNode[];
  edges: WorkflowEdge[];
  onUpdateNode: (id: string, data: Record<string, unknown>) => void;
  onClose: () => void;
}

export function NodeConfigPanel({
  nodeId,
  nodes,
  edges,
  onUpdateNode,
  onClose,
}: NodeConfigPanelProps) {
  const node = nodes.find((n) => n.id === nodeId);
  if (!node) return null;

  const nodeType = node.type;
  const Icon = NODE_ICONS[nodeType] ?? Bot;
  const colorClass = NODE_COLORS[nodeType] ?? "text-gray-400 bg-gray-800/50";

  const [label, setLabel] = useState(
    (node.data?.label as string) ?? node.type,
  );
  const [description, setDescription] = useState(
    (node.data?.description as string) ?? "",
  );

  const upstreamEdges = edges.filter((e) => e.target === nodeId);
  const downstreamEdges = edges.filter((e) => e.source === nodeId);

  function handleApply() {
    onUpdateNode(nodeId, { label, description });
  }

  return (
    <div className="w-72 bg-gray-900 border border-gray-700 rounded-lg overflow-hidden shrink-0">
      {/* Header */}
      <div className="flex items-center justify-between px-3 py-2.5 bg-gray-800/50 border-b border-gray-700">
        <div className="flex items-center gap-2">
          <span
            className={`flex items-center justify-center w-7 h-7 rounded-md ${colorClass}`}
          >
            <Icon size={14} />
          </span>
          <span className="text-sm font-medium text-gray-200 truncate max-w-[160px]">
            {node.data?.label as string}
          </span>
        </div>
        <button
          onClick={onClose}
          className="text-gray-500 hover:text-gray-300 transition-colors"
        >
          <X size={14} />
        </button>
      </div>

      {/* Body */}
      <div className="p-3 space-y-3">
        {/* Type badge */}
        <div>
          <label className="block text-xs text-gray-500 mb-1">Type</label>
          <span
            className={`inline-flex items-center gap-1 text-xs font-medium px-2 py-0.5 rounded ${colorClass}`}
          >
            <Icon size={12} />
            {nodeType}
          </span>
        </div>

        {/* Label */}
        <div>
          <label className="block text-xs text-gray-500 mb-1">Name</label>
          <input
            value={label}
            onChange={(e) => setLabel(e.target.value)}
            className="w-full px-2.5 py-1.5 bg-gray-800 border border-gray-600 rounded text-sm text-gray-200 focus:outline-none focus:border-indigo-500 transition-colors"
            placeholder="Node name"
          />
        </div>

        {/* Description */}
        <div>
          <label className="block text-xs text-gray-500 mb-1">
            Description
          </label>
          <textarea
            value={description}
            onChange={(e) => setDescription(e.target.value)}
            className="w-full px-2.5 py-1.5 bg-gray-800 border border-gray-600 rounded text-sm text-gray-200 focus:outline-none focus:border-indigo-500 transition-colors resize-none"
            placeholder="Optional description"
            rows={2}
          />
        </div>

        {/* Connections */}
        <div className="space-y-1.5">
          <div className="text-xs text-gray-500">
            Inputs:{" "}
            <span className="text-gray-300">{upstreamEdges.length}</span>
          </div>
          <div className="text-xs text-gray-500">
            Outputs:{" "}
            <span className="text-gray-300">{downstreamEdges.length}</span>
          </div>
        </div>

        {/* Apply button */}
        <button
          onClick={handleApply}
          className="w-full px-3 py-1.5 bg-indigo-600 hover:bg-indigo-500 text-white text-xs font-medium rounded-md transition-colors"
        >
          Apply
        </button>
      </div>
    </div>
  );
}
