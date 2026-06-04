import "@testing-library/jest-dom";
import { render, screen } from "@testing-library/react";
import { AgentStatusGrid } from "@/components/dashboard/AgentStatusGrid";
import type { AgentMonitorEntry } from "@/lib/api";

// Mock the hook
jest.mock("@/hooks/useAgentStatus", () => ({
  useAgentStatus: jest.fn(),
}));

import { useAgentStatus } from "@/hooks/useAgentStatus";
const mockUseAgentStatus = useAgentStatus as jest.MockedFunction<typeof useAgentStatus>;

const makeAgent = (overrides: Partial<AgentMonitorEntry> & { agent_type: string }): AgentMonitorEntry => ({
  ...overrides,
  name: (overrides.agent_type || "").replace(/_/g, " "),
  description: "",
  status: "idle",
  last_run: null,
  today: { run_count: 0, avg_duration_secs: null, total_tokens: 0, total_cost_usd: 0 },
  ...overrides,
});

const mockAgents: AgentMonitorEntry[] = [
  makeAgent({ agent_type: "social_media", status: "idle", today: { run_count: 3, avg_duration_secs: null, total_tokens: 500, total_cost_usd: 0.001 } }),
  makeAgent({ agent_type: "finance", status: "running", today: { run_count: 1, avg_duration_secs: 2.5, total_tokens: 200, total_cost_usd: 0.0005 } }),
  makeAgent({ agent_type: "competitor_research", status: "error" }),
  makeAgent({ agent_type: "orchestrator", status: "idle" }),
];

describe("AgentStatusGrid", () => {
  it("shows loading skeletons when loading=true", () => {
    mockUseAgentStatus.mockReturnValue({
      agents: [], loading: true, error: null,
      runningCount: 0, todayStats: { totalRuns: 0, totalCost: 0 },
    });
    const { container } = render(<AgentStatusGrid />);
    expect(container.querySelectorAll(".animate-pulse").length).toBeGreaterThan(0);
  });

  it("renders agent cards when loaded", () => {
    mockUseAgentStatus.mockReturnValue({
      agents: mockAgents, loading: false, error: null,
      runningCount: 1, todayStats: { totalRuns: 4, totalCost: 0.0015 },
    });
    render(<AgentStatusGrid />);
    expect(screen.getByText("Social")).toBeInTheDocument();
    expect(screen.getByText("Finance")).toBeInTheDocument();
    // "Research" may be inside a card heading; use getByText with flex match
    expect(screen.getByText((c) => c.includes("Research"))).toBeInTheDocument();
  });

  it("shows run count per agent", () => {
    mockUseAgentStatus.mockReturnValue({
      agents: mockAgents, loading: false, error: null,
      runningCount: 1, todayStats: { totalRuns: 4, totalCost: 0.0015 },
    });
    render(<AgentStatusGrid />);
    expect(screen.getAllByText(/runs/).length).toBeGreaterThan(0);
  });

  it("shows status badges", () => {
    mockUseAgentStatus.mockReturnValue({
      agents: mockAgents, loading: false, error: null,
      runningCount: 1, todayStats: { totalRuns: 4, totalCost: 0.0015 },
    });
    render(<AgentStatusGrid />);
    // "error" badge is unique (only competitor_research has error status)
    expect(screen.getByText("error")).toBeInTheDocument();
    // Multiple agents show "idle" badges
    expect(screen.getAllByText("idle").length).toBeGreaterThanOrEqual(2);
  });

  it("shows summary bar with agent count", () => {
    mockUseAgentStatus.mockReturnValue({
      agents: mockAgents, loading: false, error: null,
      runningCount: 1, todayStats: { totalRuns: 4, totalCost: 0.0015 },
    });
    const { container } = render(<AgentStatusGrid />);
    // Text is split across nested spans; check rendered HTML
    expect(container.textContent).toContain("4 agents");
    expect(container.textContent).toContain("4 runs today");
  });
});
