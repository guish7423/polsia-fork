"use client";
import { useActivityFeed } from "@/hooks/useActivityFeed";
import Link from "next/link";

const LEVEL_STYLES: Record<string, string> = {
  info: "text-blue-400",
  warning: "text-yellow-400",
  error: "text-red-400",
};

const LEVEL_DOT: Record<string, string> = {
  info: "bg-blue-400",
  warning: "bg-yellow-400",
  error: "bg-red-400",
};

export function ActivityFeed() {
  const { events, connected } = useActivityFeed(100);

  return (
    <div className="bg-gray-800 rounded-lg p-4 h-full flex flex-col">
      <div className="flex items-center justify-between mb-3">
        <h2 className="text-white font-semibold text-sm">Live Activity</h2>
        <span className={`flex items-center gap-1 text-xs ${connected ? "text-green-400" : "text-gray-500"}`}>
          <span className={`w-2 h-2 rounded-full ${connected ? "bg-green-400 animate-pulse" : "bg-gray-500"}`} />
          {connected ? "Live" : "Reconnecting…"}
        </span>
      </div>
      <div className="flex-1 overflow-y-auto space-y-2 text-sm">
        {events.length === 0 && (
          <p className="text-gray-500 text-xs">No activity yet — agents will post here.</p>
        )}
        {events.map((e, i) => (
          <div key={i} className="flex gap-2 items-start">
            <span
              className={`mt-1.5 w-2 h-2 flex-shrink-0 rounded-full ${LEVEL_DOT[e.level] ?? "bg-gray-400"}`}
            />
            <div className="min-w-0 flex-1">
              <span className={`font-medium ${LEVEL_STYLES[e.level] ?? "text-gray-300"}`}>
                {e.agent_type}
              </span>
              <span className="text-gray-400 mx-1">·</span>
              <span className="text-gray-200">{e.summary}</span>
              <div className="flex items-center gap-2 text-gray-500 text-[10px] mt-0.5">
                {e.run_id && (
                  <Link
                    href={`/agents/runs?id=${e.run_id}`}
                    className="text-indigo-400 hover:text-indigo-300"
                  >
                    run #{e.run_id}
                  </Link>
                )}
                {e.metadata?.cost_usd != null && (
                  <span className="text-amber-400">${e.metadata.cost_usd.toFixed(6)}</span>
                )}
                {e.metadata?.duration_secs != null && (
                  <span>{e.metadata.duration_secs.toFixed(1)}s</span>
                )}
              </div>
            </div>
          </div>
        ))}
      </div>
    </div>
  );
}
