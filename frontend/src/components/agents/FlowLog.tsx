"use client";
import { useEffect, useRef, useState, useCallback } from "react";

// ─── Types ──────────────────────────────────────────────────────────────────

export type StepType = "thinking" | "tool_call" | "llm_call" | "result";

export interface StepEntry {
  step: StepType;
  content: string;
  ts: string;
}

export interface FlowLogProps {
  agentType: string;
  open: boolean;
  onClose: () => void;
}

// ─── Styles per step type ──────────────────────────────────────────────────

const STEP_COLORS: Record<StepType, string> = {
  thinking: "text-blue-400",
  tool_call: "text-yellow-400",
  llm_call: "text-green-400",
  result: "text-gray-100",
};

const STEP_LABELS: Record<StepType, string> = {
  thinking: "💭",
  tool_call: "🔧",
  llm_call: "🤖",
  result: "✅",
};

const MAX_ENTRIES = 100;

// ─── Component ──────────────────────────────────────────────────────────────

export function FlowLog({ agentType, open, onClose }: FlowLogProps) {
  const [status, setStatus] = useState<"connecting" | "live" | "disconnected">("connecting");
  const [entries, setEntries] = useState<StepEntry[]>([]);
  const bottomRef = useRef<HTMLDivElement>(null);
  const esRef = useRef<EventSource | null>(null);

  const addEntry = useCallback((entry: StepEntry) => {
    setEntries((prev) => {
      const next = [...prev, entry];
      return next.length > MAX_ENTRIES ? next.slice(next.length - MAX_ENTRIES) : next;
    });
  }, []);

  useEffect(() => {
    if (!open) return;

    const es = new EventSource(`/api/v1/agents/${agentType}/stream`);
    esRef.current = es;

    es.onopen = () => setStatus("live");

    es.addEventListener("step", (e: MessageEvent) => {
      try {
        const data = JSON.parse(e.data) as StepEntry;
        addEntry(data);
      } catch {
        // ignore malformed messages
      }
    });

    es.onerror = () => {
      setStatus("disconnected");
      es.close();
    };

    return () => {
      es.close();
      esRef.current = null;
    };
  }, [open, agentType, addEntry]);

  // auto-scroll (safe for JSDOM where scrollIntoView is not available)
  useEffect(() => {
    try {
      bottomRef.current?.scrollIntoView({ behavior: "smooth" });
    } catch {
      // ignore in test environments (JSDOM)
    }
  }, [entries]);

  if (!open) return null;

  return (
    <div className="fixed inset-0 z-50 flex justify-end">
      {/* backdrop */}
      <div className="absolute inset-0 bg-black/40" onClick={onClose} />

      {/* panel */}
      <div className="relative w-full max-w-xl bg-gray-900 shadow-2xl flex flex-col border-l border-gray-700">
        {/* header */}
        <div className="flex items-center justify-between px-4 py-3 border-b border-gray-700 bg-gray-800">
          <div className="flex items-center gap-3">
            <h2 className="text-white font-semibold text-sm capitalize">
              {agentType.replace(/_/g, " ")} — Live Log
            </h2>
            <span
              className={`inline-flex items-center gap-1.5 px-2 py-0.5 rounded text-xs font-medium ${
                status === "live"
                  ? "bg-green-900/50 text-green-400"
                  : status === "connecting"
                    ? "bg-yellow-900/50 text-yellow-400"
                    : "bg-red-900/50 text-red-400"
              }`}
            >
              <span
                className={`w-1.5 h-1.5 rounded-full ${
                  status === "live"
                    ? "bg-green-400 animate-pulse"
                    : status === "connecting"
                      ? "bg-yellow-400 animate-pulse"
                      : "bg-red-400"
                }`}
              />
              {status === "live" ? "Live" : status === "connecting" ? "Connecting..." : "Disconnected"}
            </span>
          </div>
          <button
            onClick={onClose}
            className="text-gray-400 hover:text-white transition-colors text-lg leading-none px-1"
            aria-label="Close"
          >
            ✕
          </button>
        </div>

        {/* entries */}
        <div className="flex-1 overflow-y-auto p-3 font-mono text-sm leading-relaxed space-y-1 bg-gray-950">
          {entries.length === 0 && status === "live" && (
            <p className="text-gray-500 italic">Waiting for events...</p>
          )}
          {entries.length === 0 && status !== "live" && (
            <p className="text-gray-500 italic">
              {status === "connecting" ? "Connecting to stream..." : "Disconnected"}
            </p>
          )}
          {entries.map((entry, i) => (
            <div key={i} className="flex gap-2">
              <span className="text-gray-600 shrink-0 w-16 text-right text-xs">
                {entry.ts}
              </span>
              <span className="shrink-0">{STEP_LABELS[entry.step] ?? "•"}</span>
              <span className={STEP_COLORS[entry.step] ?? "text-gray-300"}>
                {entry.content}
              </span>
            </div>
          ))}
          <div ref={bottomRef} />
        </div>
      </div>
    </div>
  );
}
