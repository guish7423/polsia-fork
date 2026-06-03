import "@testing-library/jest-dom";
import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import AgentsPage from "@/app/agents/page";

// Mock next/navigation
jest.mock("next/navigation", () => ({
  useRouter: () => ({ replace: jest.fn() }),
  usePathname: () => "/agents",
}));

// Mock useAgentStatus
const mockUseAgentStatus = jest.fn();
jest.mock("@/hooks/useAgentStatus", () => ({
  useAgentStatus: () => mockUseAgentStatus(),
}));

// Mock api.post
jest.mock("@/lib/api", () => ({
  api: { post: jest.fn() },
}));

import { api } from "@/lib/api";
const mockApiPost = api.post as jest.Mock;

const makeAgent = (overrides: Record<string, unknown>) => ({
  agent_type: "orchestrator",
  name: "Orchestrator",
  description: "Daily planning and agent coordination",
  status: "idle",
  last_run: null,
  today: { run_count: 0, avg_duration_secs: null, total_tokens: 0, total_cost_usd: 0 },
  ...overrides,
});

const mockAgents = [
  makeAgent({ agent_type: "orchestrator", description: "Daily planning", last_run: { run_id: 1, status: "completed", duration_secs: 12, cost_usd: 0.001, started_at: "2026-06-01T10:00:00Z" }, today: { run_count: 5, avg_duration_secs: 10, total_tokens: 500, total_cost_usd: 0.005 } }),
  makeAgent({ agent_type: "social_media", status: "running", description: "Social media management", today: { run_count: 3, avg_duration_secs: null, total_tokens: 300, total_cost_usd: 0.003 } }),
  makeAgent({ agent_type: "finance", description: "Financial tracking", today: { run_count: 0, avg_duration_secs: null, total_tokens: 0, total_cost_usd: 0 } }),
];

describe("AgentsPage", () => {
  beforeEach(() => {
    jest.clearAllMocks();
  });

  it("shows loading skeletons while data is loading", () => {
    mockUseAgentStatus.mockReturnValue({
      agents: [], loading: true, error: null,
      runningCount: 0, todayStats: { totalRuns: 0, totalCost: 0 },
    });
    const { container } = render(<AgentsPage />);
    expect(container.querySelectorAll(".animate-pulse").length).toBe(9);
  });

  it("renders agent cards when loaded", () => {
    mockUseAgentStatus.mockReturnValue({
      agents: mockAgents, loading: false, error: null,
      runningCount: 1, todayStats: { totalRuns: 8, totalCost: 0.008 },
    });
    render(<AgentsPage />);
    expect(screen.getByText("orchestrator")).toBeInTheDocument();
    // Use getAllByText since "social media" may appear in heading + card
    expect(screen.getAllByText(/social media/i).length).toBeGreaterThanOrEqual(1);
    expect(screen.getByText("finance")).toBeInTheDocument();
  });

  it("shows agent descriptions", () => {
    mockUseAgentStatus.mockReturnValue({
      agents: mockAgents, loading: false, error: null,
      runningCount: 1, todayStats: { totalRuns: 8, totalCost: 0.008 },
    });
    render(<AgentsPage />);
    expect(screen.getByText("Daily planning")).toBeInTheDocument();
  });

  it("shows Run buttons for each agent", () => {
    mockUseAgentStatus.mockReturnValue({
      agents: mockAgents, loading: false, error: null,
      runningCount: 1, todayStats: { totalRuns: 8, totalCost: 0.008 },
    });
    render(<AgentsPage />);
    const buttons = screen.getAllByText("Run");
    expect(buttons).toHaveLength(3);
  });

  it("displays success message after triggering an agent", async () => {
    mockUseAgentStatus.mockReturnValue({
      agents: mockAgents, loading: false, error: null,
      runningCount: 1, todayStats: { totalRuns: 8, totalCost: 0.008 },
    });
    mockApiPost.mockResolvedValue({ message: "orchestrator agent triggered" });

    render(<AgentsPage />);
    const user = userEvent.setup();

    const triggerBtns = screen.getAllByText("Run");
    await user.click(triggerBtns[0]);

    await waitFor(() => {
      expect(screen.getByText("orchestrator agent triggered")).toBeInTheDocument();
    });
  });

  it("shows summary bar with agent stats", () => {
    mockUseAgentStatus.mockReturnValue({
      agents: mockAgents, loading: false, error: null,
      runningCount: 1, todayStats: { totalRuns: 8, totalCost: 0.008 },
    });
    render(<AgentsPage />);
    expect(screen.getByText(/Running Now/)).toBeInTheDocument();
    expect(screen.getByText(/\$0\.008/)).toBeInTheDocument();
  });
});
