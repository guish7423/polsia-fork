"use client";
import { Handle, Position, type NodeProps } from "@xyflow/react";
import { Wrench } from "lucide-react";

export function ToolNode({ data, selected }: NodeProps) {
  return (
    <div
      className={`bg-gray-800 border-2 rounded-xl p-3 w-[180px] shadow-lg transition-shadow ${
        selected
          ? "border-emerald-400 shadow-emerald-500/20 ring-1 ring-emerald-500/30"
          : "border-emerald-500/50"
      }`}
    >
      <Handle type="target" position={Position.Top} className="!bg-emerald-400 !w-2.5 !h-2.5" />
      <div className="flex items-center gap-2">
        <div className="p-1.5 bg-emerald-500/20 rounded-lg">
          <Wrench size={16} className="text-emerald-400" />
        </div>
        <div className="flex-1 min-w-0">
          <p className="text-white text-sm font-medium truncate">
            {(data.label as string) ?? "Tool"}
          </p>
          <p className="text-gray-400 text-[10px] truncate">
            {(data.tool_name as string) ?? "tool"}
          </p>
        </div>
      </div>
      <Handle type="source" position={Position.Bottom} className="!bg-emerald-400 !w-2.5 !h-2.5" />
    </div>
  );
}
