"use client";
import { Handle, Position, type NodeProps } from "@xyflow/react";
import { Zap } from "lucide-react";

export function TriggerNode({ data, selected }: NodeProps) {
  return (
    <div className="relative w-[180px] h-[80px] flex items-center justify-center">
      {/* Diamond background via clip-path */}
      <div
        className={`absolute inset-0 bg-gray-800 transition-shadow ${
          selected
            ? "ring-1 ring-amber-500/30"
            : ""
        }`}
        style={{
          clipPath: "polygon(50% 0%, 100% 50%, 50% 100%, 0% 50%)",
          border: `2px solid ${selected ? "#f59e0b" : "#f59e0b80"}`,
        }}
      />
      {/* Inner fill */}
      <div
        className="absolute inset-[3px] bg-gray-800"
        style={{ clipPath: "polygon(50% 0%, 100% 50%, 50% 100%, 0% 50%)" }}
      />
      {/* Content */}
      <div className="relative z-10 flex items-center gap-2 px-4">
        <div className="p-1 bg-amber-500/20 rounded-md">
          <Zap size={14} className="text-amber-400" />
        </div>
        <div className="min-w-0">
          <p className="text-white text-sm font-medium truncate">
            {(data.label as string) ?? "Trigger"}
          </p>
          <p className="text-gray-400 text-[10px] truncate">
            {(data.trigger_type as string) ?? "event"}
          </p>
        </div>
      </div>
      <Handle type="source" position={Position.Bottom} className="!bg-amber-400 !w-2.5 !h-2.5" />
    </div>
  );
}
