"use client";
import { Handle, Position, type NodeProps } from "@xyflow/react";
import { Check } from "lucide-react";

export function OutputNode({ data, selected }: NodeProps) {
  return (
    <div
      className={`bg-gray-800 border-2 rounded-xl p-3 w-[180px] shadow-lg transition-shadow ${
        selected
          ? "border-gray-400 shadow-gray-500/20 ring-1 ring-gray-500/30"
          : "border-gray-500/50"
      }`}
    >
      <Handle type="target" position={Position.Top} className="!bg-gray-400 !w-2.5 !h-2.5" />
      <div className="flex items-center gap-2">
        <div className="p-1.5 bg-gray-500/20 rounded-lg">
          <Check size={16} className="text-gray-400" />
        </div>
        <div className="flex-1 min-w-0">
          <p className="text-white text-sm font-medium truncate">
            {(data.label as string) ?? "Output"}
          </p>
          <p className="text-gray-400 text-[10px] truncate">
            {(data.output_name as string) ?? "output"}
          </p>
        </div>
      </div>
    </div>
  );
}
