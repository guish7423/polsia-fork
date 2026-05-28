"use client";

import { useMemo, useState, useEffect, useRef } from "react";
import Link from "next/link";

// ─── Mock Agent Data ──────────────────────────────────────────────────────────

const AGENTS = [
  { type: "orchestrator", label: "Orchestrator / CEO", icon: "👑", color: "from-violet-500 to-purple-600" },
  { type: "business_planning", label: "Business Planning", icon: "📊", color: "from-blue-500 to-indigo-600" },
  { type: "competitor_research", label: "Competitor Research", icon: "🔍", color: "from-cyan-500 to-teal-600" },
  { type: "social_media", label: "Social Media", icon: "📱", color: "from-pink-500 to-rose-600" },
  { type: "ads_management", label: "Ads Management", icon: "📢", color: "from-orange-500 to-amber-600" },
  { type: "email_outreach", label: "Email Outreach", icon: "✉️", color: "from-emerald-500 to-green-600" },
  { type: "customer_support", label: "Customer Support", icon: "💬", color: "from-sky-500 to-blue-600" },
  { type: "code_generation", label: "Code Generation", icon: "💻", color: "from-gray-500 to-slate-600" },
  { type: "finance", label: "Finance", icon: "💰", color: "from-yellow-500 to-amber-600" },
  { type: "deployment", label: "Deployment", icon: "🚀", color: "from-red-500 to-orange-600" },
];

const STATUSES = ["idle", "running", "completed", "failed"] as const;
const STATUS_STYLE: Record<string, string> = {
  completed: "bg-green-500/20 text-green-400 border-green-500/30",
  running: "bg-blue-500/20 text-blue-400 border-blue-500/30 animate-pulse",
  failed: "bg-red-500/20 text-red-400 border-red-500/30",
  idle: "bg-gray-700/40 text-gray-400 border-gray-600/30",
};

const SAMPLE_EVENTS = [
  { agent: "orchestrator", action: "completed", summary: "Daily plan generated — 12 tasks scheduled", level: "success" },
  { agent: "social_media", action: "completed", summary: "Posted to X/Twitter: Industry insights thread", level: "success" },
  { agent: "code_generation", action: "running", summary: "Implementing Stripe webhook handler", level: "info" },
  { agent: "competitor_research", action: "completed", summary: "Competitor pricing update detected for ProductX", level: "warning" },
  { agent: "finance", action: "completed", summary: "Daily revenue snapshot: $847.32", level: "success" },
  { agent: "email_outreach", action: "running", summary: "Sending batch 3/5: 247 prospects", level: "info" },
  { agent: "ads_management", action: "completed", summary: "Campaign ROAS improved from 2.1x to 3.4x", level: "success" },
  { agent: "customer_support", action: "completed", summary: "Resolved 14 tickets, avg response 3.2min", level: "success" },
  { agent: "orchestrator", action: "running", summary: "Reviewing evening reports from all agents", level: "info" },
  { agent: "social_media", action: "running", summary: "Generating LinkedIn article draft", level: "info" },
  { agent: "deployment", action: "completed", summary: "Hotfix v1.2.3 deployed to production", level: "success" },
  { agent: "finance", action: "warning", summary: "Monthly burn rate approaching 80% of budget", level: "warning" },
  { agent: "code_generation", action: "completed", summary: "API rate limiting middleware implemented", level: "success" },
  { agent: "business_planning", action: "completed", summary: "Q3 growth strategy draft ready for review", level: "success" },
  { agent: "email_outreach", action: "completed", summary: "235 emails sent, 12.4% open rate", level: "success" },
];

// ─── Animated Counter ─────────────────────────────────────────────────────────

function AnimatedNumber({ value, suffix = "", decimals = 0 }: { value: number; suffix?: string; decimals?: number }) {
  const [display, setDisplay] = useState(0);
  const ref = useRef<number | null>(null);

  useEffect(() => {
    const start = performance.now();
    const duration = 1500 + Math.random() * 1000;

    function tick(now: number) {
      const elapsed = now - start;
      const progress = Math.min(elapsed / duration, 1);
      // Ease out cubic
      const eased = 1 - Math.pow(1 - progress, 3);
      setDisplay(Math.round(value * eased * 10 ** decimals) / 10 ** decimals);
      if (progress < 1) ref.current = requestAnimationFrame(tick);
    }

    ref.current = requestAnimationFrame(tick);
    return () => { if (ref.current) cancelAnimationFrame(ref.current); };
  }, [value, decimals]);

  return <>{display.toLocaleString("en-US", { minimumFractionDigits: decimals, maximumFractionDigits: decimals })}{suffix}</>;
}

// ─── Activity Item ────────────────────────────────────────────────────────────

function ActivityItem({ event, index }: { event: typeof SAMPLE_EVENTS[0]; index: number }) {
  const DOT_COLORS: Record<string, string> = {
    success: "bg-green-400", error: "bg-red-400", warning: "bg-yellow-400", info: "bg-blue-400",
  };
  const TEXT_COLORS: Record<string, string> = {
    success: "text-green-400", error: "text-red-400", warning: "text-yellow-400", info: "text-blue-400",
  };

  return (
    <div
      className="flex gap-3 items-start animate-slide-in"
      style={{ animationDelay: `${index * 80}ms` }}
    >
      <span className={`mt-1.5 w-2 h-2 flex-shrink-0 rounded-full ${DOT_COLORS[event.level] ?? "bg-gray-400"}`} />
      <div className="min-w-0">
        <span className={`text-xs font-semibold ${TEXT_COLORS[event.level] ?? "text-gray-300"}`}>
          {event.agent}
        </span>
        <span className="text-gray-500 mx-1">·</span>
        <span className="text-gray-300 text-sm">{event.summary}</span>
      </div>
    </div>
  );
}

// ─── Demo Page ────────────────────────────────────────────────────────────────

export default function DemoPage() {
  const [agentStatuses, setAgentStatuses] = useState(
    AGENTS.map((a) => ({ ...a, status: "idle" as string, tasksToday: Math.floor(Math.random() * 8) }))
  );
  const [events, setEvents] = useState<typeof SAMPLE_EVENTS>([]);
  const eventIdx = useRef(0);

  // Simulate agent cycling
  useEffect(() => {
    const interval = setInterval(() => {
      setAgentStatuses((prev) =>
        prev.map((a) => {
          const roll = Math.random();
          if (roll < 0.15) return { ...a, status: "running" };
          if (roll < 0.3 && a.status === "running") return { ...a, status: "completed", tasksToday: a.tasksToday + 1 };
          if (roll < 0.35 && a.status === "running") return { ...a, status: "failed" };
          if (roll < 0.42) return { ...a, status: "idle" };
          return a;
        })
      );
    }, 3000);
    return () => clearInterval(interval);
  }, []);

  // Simulate activity feed
  useEffect(() => {
    const timer = setInterval(() => {
      if (eventIdx.current < SAMPLE_EVENTS.length) {
        setEvents((prev) => [SAMPLE_EVENTS[eventIdx.current], ...prev].slice(0, 20));
        eventIdx.current++;
      } else {
        eventIdx.current = 0;
      }
    }, 2000);
    return () => clearInterval(timer);
  }, []);

  // Mock KPIs
  const kpis = useMemo(() => ({
    mrr: 8473,
    arr: 101676,
    activeCustomers: 47,
    churnRate: 3.2,
    tasksToday: 87,
    tasksCompleted: 71,
    tasksFailed: 4,
  }), []);

  return (
    <div className="min-h-screen bg-gray-950 text-white overflow-x-hidden">
      {/* ─── Hero ────────────────────────────────────────────── */}
      <style jsx global>{`
        @keyframes slide-in {
          from { opacity: 0; transform: translateY(8px); }
          to { opacity: 1; transform: translateY(0); }
        }
        .animate-slide-in { animation: slide-in 0.4s ease-out both; }
      `}</style>

      <header className="sticky top-0 z-50 backdrop-blur-xl bg-gray-950/80 border-b border-gray-800">
        <div className="max-w-7xl mx-auto px-4 h-14 flex items-center justify-between">
          <div className="flex items-center gap-3">
            <span className="text-xl font-bold">
              Polsia <span className="text-violet-400">Fork</span>
            </span>
            <span className="px-2 py-0.5 bg-violet-500/20 text-violet-300 text-xs rounded-full font-medium">
              Live Demo
            </span>
          </div>
          <div className="flex items-center gap-4">
            <Link
              href="/"
              className="text-sm text-gray-400 hover:text-white transition-colors"
            >
              Back to App
            </Link>
            <a
              href="https://github.com/guish7423/polsia-fork"
              target="_blank"
              rel="noopener noreferrer"
              className="text-sm bg-gray-800 hover:bg-gray-700 px-4 py-1.5 rounded-lg transition-colors border border-gray-700"
            >
              GitHub
            </a>
          </div>
        </div>
      </header>

      <main className="max-w-7xl mx-auto px-4 py-8 space-y-8">
        {/* ─── KPI Grid ──────────────────────────────────────── */}
        <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
          <div className="bg-gray-900/80 border border-gray-800 rounded-xl p-5 hover:border-violet-500/30 transition-all">
            <p className="text-gray-400 text-xs uppercase tracking-wider mb-1">Tasks Today</p>
            <p className="text-3xl font-bold text-white">
              <AnimatedNumber value={kpis.tasksToday} />
            </p>
            <p className="text-sm text-green-400 mt-1">
              <AnimatedNumber value={kpis.tasksCompleted} /> completed ·
              <AnimatedNumber value={kpis.tasksFailed} /> failed
            </p>
          </div>
          <div className="bg-gray-900/80 border border-gray-800 rounded-xl p-5 hover:border-violet-500/30 transition-all">
            <p className="text-gray-400 text-xs uppercase tracking-wider mb-1">MRR</p>
            <p className="text-3xl font-bold text-green-400">
              $<AnimatedNumber value={kpis.mrr} />
            </p>
            <p className="text-sm text-gray-500 mt-1">
              ARR $<AnimatedNumber value={kpis.arr} />
            </p>
          </div>
          <div className="bg-gray-900/80 border border-gray-800 rounded-xl p-5 hover:border-violet-500/30 transition-all">
            <p className="text-gray-400 text-xs uppercase tracking-wider mb-1">Active Customers</p>
            <p className="text-3xl font-bold text-white">
              <AnimatedNumber value={kpis.activeCustomers} />
            </p>
            <p className="text-sm text-gray-500 mt-1">
              <span className="text-green-400">↑ 12%</span> vs last month
            </p>
          </div>
          <div className="bg-gray-900/80 border border-gray-800 rounded-xl p-5 hover:border-violet-500/30 transition-all">
            <p className="text-gray-400 text-xs uppercase tracking-wider mb-1">Churn Rate</p>
            <p className="text-3xl font-bold text-yellow-400">
              <AnimatedNumber value={kpis.churnRate} decimals={1} />%
            </p>
            <p className="text-sm text-gray-500 mt-1">
              <span className="text-green-400">↓ 0.8%</span> target: &lt;5%
            </p>
          </div>
        </div>

        {/* ─── Agent Grid + Activity ─────────────────────────── */}
        <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
          {/* Agent Grid */}
          <div>
            <h2 className="text-sm font-semibold text-gray-300 uppercase tracking-wider mb-3">
              AI Agent Team · {agentStatuses.filter((a) => a.status === "running").length} running
            </h2>
            <div className="grid grid-cols-2 sm:grid-cols-3 gap-3">
              {agentStatuses.map((a) => {
                const style = STATUS_STYLE[a.status] ?? STATUS_STYLE.idle;
                return (
                  <div
                    key={a.type}
                    className={`bg-gray-900/60 border rounded-xl p-4 transition-all duration-500 ${style}`}
                  >
                    <div className="text-xl mb-2">{a.icon}</div>
                    <p className="text-sm font-medium text-white truncate">{a.label}</p>
                    <div className="flex items-center gap-2 mt-2">
                      <span className={`inline-block w-2 h-2 rounded-full ${
                        a.status === "running" ? "bg-blue-400 animate-pulse" :
                        a.status === "completed" ? "bg-green-400" :
                        a.status === "failed" ? "bg-red-400" : "bg-gray-500"
                      }`} />
                      <span className="text-xs capitalize">{a.status}</span>
                    </div>
                    <p className="text-gray-500 text-xs mt-1">{a.tasksToday} tasks today</p>
                  </div>
                );
              })}
            </div>
          </div>

          {/* Activity Feed */}
          <div>
            <h2 className="text-sm font-semibold text-gray-300 uppercase tracking-wider mb-3">
              Live Activity · <span className="text-green-400">Simulated</span>
            </h2>
            <div className="bg-gray-900/60 border border-gray-800 rounded-xl p-4 max-h-[520px] overflow-y-auto space-y-3">
              {events.length === 0 ? (
                <p className="text-gray-500 text-sm text-center py-8">
                  Agents are working — activity will appear here…
                </p>
              ) : (
                events.map((ev, i) => (
                  <ActivityItem key={`${ev.agent}-${events.length - i}`} event={ev} index={i} />
                ))
              )}
            </div>
          </div>
        </div>

        {/* ─── CTA ──────────────────────────────────────────── */}
        <div className="text-center py-12">
          <div className="inline-flex items-center gap-2 px-3 py-1 bg-violet-500/10 border border-violet-500/30 rounded-full text-violet-300 text-xs mb-4">
            ✦ Powered by AI
          </div>
          <h2 className="text-3xl font-bold mb-3">
            Ready to automate <span className="text-violet-400">your company</span>?
          </h2>
          <p className="text-gray-400 max-w-lg mx-auto mb-6">
            10 AI agents working 24/7 — coding, marketing, support, and operations.
            Deploy for free on your own server.
          </p>
          <div className="flex gap-3 justify-center">
            <a
              href="https://github.com/guish7423/polsia-fork"
              target="_blank"
              rel="noopener noreferrer"
              className="inline-flex items-center gap-2 px-6 py-3 bg-violet-600 hover:bg-violet-500 text-white font-semibold rounded-xl transition-all shadow-lg shadow-violet-600/20"
            >
              Deploy Free →
            </a>
            <Link
              href="/"
              className="inline-flex items-center gap-2 px-6 py-3 bg-gray-800 hover:bg-gray-700 text-white font-semibold rounded-xl border border-gray-700 transition-all"
            >
              Launch App
            </Link>
          </div>
        </div>
      </main>
    </div>
  );
}
