import "@testing-library/jest-dom";
import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import AgentsPage from "@/app/agents/page";

// Mock next/navigation
jest.mock("next/navigation", () => ({
  useRouter: () => ({ replace: jest.fn() }),
  usePathname: () => "/agents",
}));

// Mock i18n
const mockT = jest.fn();
jest.mock("@/lib/i18n", () => ({
  useI18n: () => ({ t: mockT }),
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

const mockStatuses = [
  { agent_type: "orchestrator", last_run_status: "completed", last_run_at: "2026-05-31T10:00:00Z", tasks_today: 5, tasks_total: 120 },
  { agent_type: "social_media", last_run_status: "running", last_run_at: null, tasks_today: 3, tasks_total: 45 },
  { agent_type: "finance", last_run_status: "failed", last_run_at: "2026-05-30T08:00:00Z", tasks_today: 0, tasks_total: 200 },
];

describe("AgentsPage", () => {
  beforeEach(() => {
    jest.clearAllMocks();
    mockT.mockImplementation((key: string) => {
      const map: Record<string, string> = {
        "agents.title": "Agents",
        "agents.run_now": "Run Now",
        "agents.triggering": "Triggering…",
        "agents.last_run": "Last run",
        "agents.tasks_today": "tasks today",
        "agents.never": "Never",
        "agent.orchestrator": "Generates daily task plans",
        "agent.social_media": "Drafts and posts tweets",
        "agent.finance": "Monitors Stripe revenue",
      };
      return map[key] ?? key;
    });
  });

  it("shows loading skeletons while data is loading", () => {
    mockUseAgentStatus.mockReturnValue({ statuses: [], loading: true, error: null });
    const { container } = render(<AgentsPage />);
    expect(container.querySelectorAll(".animate-pulse").length).toBe(9);
  });

  it("renders agent cards when loaded", () => {
    mockUseAgentStatus.mockReturnValue({ statuses: mockStatuses, loading: false, error: null });
    render(<AgentsPage />);
    expect(screen.getByText("orchestrator")).toBeInTheDocument();
    // agent_type replace(/_/g, " ") is applied in the component
    expect(screen.getByText("social media")).toBeInTheDocument();
    expect(screen.getByText("finance")).toBeInTheDocument();
  });

  it("shows agent descriptions via i18n", () => {
    mockUseAgentStatus.mockReturnValue({ statuses: mockStatuses, loading: false, error: null });
    render(<AgentsPage />);
    expect(screen.getByText("Generates daily task plans")).toBeInTheDocument();
  });

  it("shows run buttons for each agent", () => {
    mockUseAgentStatus.mockReturnValue({ statuses: mockStatuses, loading: false, error: null });
    render(<AgentsPage />);
    const buttons = screen.getAllByText("Run Now");
    expect(buttons).toHaveLength(3);
  });

  it("displays success message after triggering an agent", async () => {
    mockUseAgentStatus.mockReturnValue({ statuses: mockStatuses, loading: false, error: null });
    mockApiPost.mockResolvedValue({ message: "Orchestrator agent triggered successfully" });

    render(<AgentsPage />);
    const user = userEvent.setup();

    const triggerBtns = screen.getAllByText("Run Now");
    await user.click(triggerBtns[0]);

    await waitFor(() => {
      expect(screen.getByText("Orchestrator agent triggered successfully")).toBeInTheDocument();
    });
  });

  it("displays error message when trigger fails", async () => {
    mockUseAgentStatus.mockReturnValue({ statuses: mockStatuses, loading: false, error: null });
    mockApiPost.mockRejectedValue(new Error("Agent not available"));

    render(<AgentsPage />);
    const user = userEvent.setup();

    const triggerBtns = screen.getAllByText("Run Now");
    await user.click(triggerBtns[0]);

    await waitFor(() => {
      expect(screen.getByText("Error: Agent not available")).toBeInTheDocument();
    });
  });

  it("shows last run time for agents", () => {
    mockUseAgentStatus.mockReturnValue({ statuses: mockStatuses, loading: false, error: null });
    render(<AgentsPage />);

    expect(screen.getAllByText(/Last run/).length).toBeGreaterThan(0);
  });

  it("shows 'Never' for agents that never ran", () => {
    mockUseAgentStatus.mockReturnValue({ statuses: mockStatuses, loading: false, error: null });
    render(<AgentsPage />);

    // "Never" is embedded inside a longer text node with "Last run:" etc.
    expect(screen.getByText(/Never/)).toBeInTheDocument();
  });
});
