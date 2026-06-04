/**
 * @jest-environment node
 *
 * Verify new API types compile and match expected shapes.
 * Types are compile-time constructs, so we verify their runtime
 * compatibility by constructing conformant objects.
 */
import {
  type QuotaData,
  type QuotaDimension,
  type MCPTool,
  type Plugin,
  type AuditEntry,
  type SchedulerStatus,
  type SandboxExecution,
  type SandboxSummary,
  type MarketplaceAgent,
  type AuditEntryListResponse,
} from "@/lib/api";

describe("QuotaData type shape", () => {
  it("constructs a valid QuotaDimension", () => {
    const dim: QuotaDimension = {
      allowed: true,
      reason: "within_limit",
      current: 5,
      limit: 10,
      usage_pct: 50.0,
    };
    expect(dim.allowed).toBe(true);
    expect(dim.current).toBeLessThanOrEqual(dim.limit);
  });

  it("constructs a valid QuotaData", () => {
    const data: QuotaData = {
      tenant_id: 1,
      agents: { allowed: true, reason: "", current: 3, limit: 10, usage_pct: 30 },
      tasks: { allowed: true, reason: "", current: 50, limit: 200, usage_pct: 25 },
      tokens: { allowed: true, reason: "", current: 10000, limit: 100000, usage_pct: 10 },
      cost: { allowed: true, reason: "", current: 5.5, limit: 100, usage_pct: 5.5 },
    };
    expect(data.tenant_id).toBe(1);
    expect(Object.keys(data)).toEqual(["tenant_id", "agents", "tasks", "tokens", "cost"]);
  });
});

describe("MCPTool type shape", () => {
  it("constructs a valid MCPTool", () => {
    const tool: MCPTool = {
      id: 1,
      name: "search",
      description: "Search the web",
      endpoint: "https://api.example.com/search",
      enabled: true,
    };
    expect(tool.name).toBe("search");
  });
});

describe("Plugin type shape", () => {
  it("constructs a valid Plugin", () => {
    const plugin: Plugin = {
      id: 1,
      tenant_id: 1,
      name: "Slack Notifier",
      description: "Sends notifications to Slack",
      version: "1.0",
      webhook_url: "https://hooks.slack.com/xxx",
      manifest: { version: "1.0", hooks: ["task.completed"] },
      enabled: true,
      config: { channel: "#general" },
      last_called_at: "2026-06-04T12:00:00",
      last_error: null,
      created_at: "2026-01-01T00:00:00",
    };
    expect(plugin.name).toBe("Slack Notifier");
    expect(plugin.enabled).toBe(true);
  });
});

describe("AuditEntry type shape", () => {
  it("constructs a valid AuditEntry", () => {
    const entry: AuditEntry = {
      id: 1,
      entry_type: "task_run",
      entry_id: 42,
      action: "created",
      hash: "abc123",
      previous_hash: "def456",
      created_at: "2026-06-04T12:00:00",
    };
    expect(entry.hash).toHaveLength(6);
  });

  it("constructs an AuditEntryListResponse", () => {
    const resp: AuditEntryListResponse = {
      entries: [
        { id: 1, entry_type: "task", entry_id: 1, action: "create", hash: "a", previous_hash: "", created_at: null },
      ],
      total: 1,
    };
    expect(resp.entries).toHaveLength(1);
  });
});

describe("SchedulerStatus type shape", () => {
  it("constructs a valid SchedulerStatus", () => {
    const status: SchedulerStatus = {
      tenant_id: 1,
      running: 2,
      pending: 5,
      queued: 0,
      load_score: 7.5,
      agents_limit: 20,
      threshold_exceeded: false,
    };
    expect(status.running + status.pending).toBe(7);
  });
});

describe("SandboxExecution type shape", () => {
  it("constructs a valid SandboxExecution", () => {
    const exec: SandboxExecution = {
      id: 1,
      action_type: "delete",
      agent_type: "finance",
      summary: "Delete old records",
      payload: { record_ids: [1, 2, 3] },
      rule_id: "block_delete",
      status: "pending",
      created_at: "2026-06-04T12:00:00",
    };
    expect(exec.id).toBe(1);
    expect(exec.status).toBe("pending");
  });
});

describe("SandboxSummary type shape", () => {
  it("constructs a valid SandboxSummary", () => {
    const summary: SandboxSummary = {
      sandbox_enabled: true,
      total_pending: 3,
      pending_approval: 2,
      approved: 1,
      total_rejected: 0,
      recent: [],
      rules: 4,
    };
    expect(summary.pending_approval).toBeLessThanOrEqual(summary.total_pending);
  });
});

describe("MarketplaceAgent type shape", () => {
  it("constructs a valid MarketplaceAgent", () => {
    const agent: MarketplaceAgent = {
      name: "Finance Agent",
      type: "finance",
      description: "Monitors revenue and expenses",
      installed: true,
      version: "1.0.0",
    };
    expect(agent.type).toBe("finance");
  });
});
