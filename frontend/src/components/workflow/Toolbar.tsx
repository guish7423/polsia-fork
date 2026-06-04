"use client";
import { type DragEvent } from "react";
import { Bot, Wrench, Zap, Check } from "lucide-react";

type ToolItem = {
  type: string;
  label: string;
  icon: typeof Bot;
  color: string;
  bgColor: string;
};

const TOOLS: ToolItem[] = [
  {
    type: "agent",
    label: "Agent",
    icon: Bot,
    color: "text-indigo-400",
    bgColor: "border-indigo-500/30 hover:border-indigo-400 hover:bg-indigo-500/10",
  },
  {
    type: "tool",
    label: "Tool",
    icon: Wrench,
    color: "text-emerald-400",
    bgColor: "border-emerald-500/30 hover:border-emerald-400 hover:bg-emerald-500/10",
  },
  {
    type: "trigger",
    label: "Trigger",
    icon: Zap,
    color: "text-amber-400",
    bgColor: "border-amber-500/30 hover:border-amber-400 hover:bg-amber-500/10",
  },
  {
    type: "output",
    label: "Output",
    icon: Check,
    color: "text-gray-400",
    bgColor: "border-gray-500/30 hover:border-gray-400 hover:bg-gray-500/10",
  },
];

export function Toolbar() {
  const onDragStart = (event: DragEvent, nodeType: string) => {
    event.dataTransfer.setData("application/reactflow", nodeType);
    event.dataTransfer.effectAllowed = "move";
  };

  return (
    <div className="flex items-center gap-2 px-4 py-2.5 bg-gray-900/90 border-b border-gray-700/50">
      <span className="text-[10px] text-gray-500 font-semibold uppercase tracking-widest mr-1">
        Nodes
      </span>
      <div className="w-px h-5 bg-gray-700" />
      {TOOLS.map(({ type, label, icon: Icon, color, bgColor }) => (
        <button
          key={type}
          draggable
          onDragStart={(e) => onDragStart(e, type)}
          className={`flex items-center gap-1.5 px-3 py-1.5 rounded-lg bg-gray-800/80 border text-xs font-medium transition-colors cursor-grab active:cursor-grabbing select-none ${color} ${bgColor}`}
          title={`Drag to add ${label} node`}
        >
          <Icon size={14} />
          {label}
        </button>
      ))}
    </div>
  );
}
