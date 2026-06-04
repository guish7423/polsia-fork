"use client";
import { Handle, Position, type NodeProps } from "@xyflow/react";
import { Bot } from "lucide-react";

export function AgentNode({ data, selected }: NodeProps) {
  return (
    <div
      className={`bg-gray-800 border-2 rounded-xl p-3 w-[180px] shadow-lg transition-shadow ${
        selected
          ? "border-indigo-400 shadow-indigo-500/20 ring-1 ring-indigo-500/30"
          : "border-indigo-500/50"
      }`}
    >
      <Handle type="target" position={Position.Top} className="!bg-indigo-400 !w-2.5 !h-2.5" />
      <div className="flex items-center gap-2">
        <div className="p-1.5 bg-indigo-500/20 rounded-lg">
          <Bot size={16} className="text-indigo-400" />
        </div>
        <div className="flex-1 min-w-0">
          <p className="text-white text-sm font-medium truncate">
            {(data.label as string) ?? "Agent"}
          </p>
          <p className="text-gray-400 text-[10px] truncate">
            {(data.agent_type as string) ?? "agent"}
          </p>
        </div>
      </div>
      <Handle type="source" position={Position.Bottom} className="!bg-indigo-400 !w-2.5 !h-2.5" />
    </div>
  );
}
