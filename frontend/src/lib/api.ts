const API_URL = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8001";
const API_KEY = process.env.NEXT_PUBLIC_API_KEY ?? "";

async function apiFetch<T>(path: string, options: RequestInit = {}): Promise<T> {
  const res = await fetch(`${API_URL}/api/v1${path}`, {
    ...options,
    headers: {
      "Content-Type": "application/json",
      "X-API-Key": API_KEY,
      ...options.headers,
    },
  });
  if (!res.ok) {
    const detail = await res.text().catch(() => res.statusText);
    throw new Error(`API ${res.status}: ${detail}`);
  }
  return res.json() as Promise<T>;
}

export const api = {
  get: <T>(path: string) => apiFetch<T>(path),
  post: <T>(path: string, body?: unknown) =>
    apiFetch<T>(path, { method: "POST", body: JSON.stringify(body) }),
  put: <T>(path: string, body?: unknown) =>
    apiFetch<T>(path, { method: "PUT", body: JSON.stringify(body) }),
};

// ─── Agent Monitor ──────────────────────────────────────────────────────────

export type AgentMonitorEntry = {
  agent_type: string;
  name: string;
  description: string;
  status: "idle" | "running" | "error";
  last_run: {
    run_id: number;
    status: string;
    duration_secs: number | null;
    cost_usd: number | null;
    started_at: string | null;
  } | null;
  today: {
    run_count: number;
    avg_duration_secs: number | null;
    total_tokens: number;
    total_cost_usd: number;
  };
};

// ─── Agent Runs ─────────────────────────────────────────────────────────────

export type AgentRunSummary = {
  id: number;
  agent_type: string;
  run_type: string;
  status: string;
  tokens_used: number | null;
  cost_usd: number | null;
  duration_secs: number | null;
  llm_call_count: number | null;
  started_at: string | null;
  ended_at: string | null;
};

export type AgentRunListResponse = {
  total: number;
  limit: number;
  offset: number;
  runs: AgentRunSummary[];
};

export type LlmCallSummary = {
  id: number;
  provider: string;
  model: string;
  input_tokens: number;
  output_tokens: number;
  cost_usd: number;
  duration_ms: number;
  success: boolean;
  error: string | null;
  created_at: string | null;
};

export type AgentRunDetail = {
  id: number;
  task_id: number | null;
  agent_type: string;
  run_type: string;
  status: string;
  input_context: Record<string, unknown> | null;
  output: Record<string, unknown> | null;
  telemetry: {
    tokens_used: number | null;
    cost_usd: number | null;
    duration_secs: number | null;
    llm_call_count: number | null;
  };
  execution_spans: Record<string, unknown> | null;
  started_at: string | null;
  ended_at: string | null;
  llm_calls: LlmCallSummary[];
};

// ─── Activity / WebSocket ───────────────────────────────────────────────────

export type ActivityEvent = {
  agent_type: string;
  action: string;
  summary: string;
  level: "info" | "warning" | "error";
  run_id?: number;
  metadata?: {
    duration_secs?: number;
    cost_usd?: number;
    status?: string;
  };
};

// ─── Usage ──────────────────────────────────────────────────────────────────

export type UsageStats = {
  total_calls: number;
  total_cost_usd: number;
  total_input_tokens: number;
  total_output_tokens: number;
  total_duration_ms: number;
  success_rate: number;
};

export type UsageRecentCall = {
  id: number;
  provider: string;
  model: string;
  input_tokens: number;
  output_tokens: number;
  cost_usd: number;
  duration_ms: number;
  success: boolean;
  error: string | null;
  task_category: string;
  created_at: string;
};

// ─── Legacy (backward compat) ───────────────────────────────────────────────

/** @deprecated Use AgentMonitorEntry / AgentRunSummary instead. */
export type AgentStatus = {
  agent_type: string;
  last_run_at: string | null;
  last_run_status: string | null;
  tasks_today: number;
  tasks_total: number;
};

export type DashboardSummary = {
  tasks_today_total: number;
  tasks_today_completed: number;
  tasks_today_pending: number;
  tasks_today_failed: number;
  active_agents: string[];
  kpis: Record<string, unknown>;
  last_report_date: string | null;
};

export type Task = {
  id: number;
  title: string;
  agent_type: string;
  status: string;
  priority: number;
  created_at: string;
};

export type FinanceSummary = {
  mrr_cents: number;
  arr_cents: number;
  active_subscribers: number;
  total_ad_spend_usd: number;
  total_expenses_month_cents: number;
  stripe_balance_cents: number;
  last_snapshot_date: string | null;
};

export type MeInfo = {
  email: string;
  api_key: string;
  plan: string;
  status: string;
  active: boolean;
  agents_limit: number;
  tasks_monthly_limit: number;
  onboarding_completed: boolean;
  current_period_end: string | null;
};
