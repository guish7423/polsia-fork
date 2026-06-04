import "@testing-library/jest-dom";
import { render, screen, act } from "@testing-library/react";
import DashboardPage from "@/app/dashboard/page";
import { I18nProvider } from "@/lib/i18n";
import { api } from "@/lib/api";
import type { DashboardSummary } from "@/lib/api";

// ─── Mock child components that make network calls ─────────────────────────

jest.mock("@/components/dashboard/GlobalAlertBanner", () => ({
  GlobalAlertBanner: () => <div data-testid="alert-banner" />,
}));

jest.mock("@/components/dashboard/SystemHealthCard", () => ({
  SystemHealthCard: () => <div data-testid="health-card" />,
}));

jest.mock("@/components/dashboard/AgentStatusGrid", () => ({
  AgentStatusGrid: () => <div data-testid="agent-grid" />,
}));

jest.mock("@/components/dashboard/ActivityFeed", () => ({
  ActivityFeed: () => <div data-testid="activity-feed" />,
}));

// ─── Mock api.get ──────────────────────────────────────────────────────────

const mockGet = jest.spyOn(api, "get") as jest.Mock;

const MOCK_SUMMARY: DashboardSummary = {
  tasks_today_total: 42,
  tasks_today_completed: 35,
  tasks_today_pending: 5,
  tasks_today_failed: 2,
  active_agents: ["orchestrator", "social_media"],
  kpis: {
    mrr_usd: 12500,
    active_customers: 48,
    churn_rate: 3.2,
  },
  last_report_date: "2026-06-04",
};

function renderPage() {
  return render(
    <I18nProvider>
      <DashboardPage />
    </I18nProvider>,
  );
}

beforeEach(() => {
  jest.useFakeTimers();
  mockGet.mockReset();
  mockGet.mockResolvedValue(MOCK_SUMMARY);
});

afterEach(() => {
  jest.useRealTimers();
});

// ─── Tests ─────────────────────────────────────────────────────────────────

describe("DashboardAutoRefresh", () => {
  it("1. fetches dashboard summary on mount and renders KPIs", async () => {
    await act(async () => {
      renderPage();
      await jest.runAllTimersAsync();
    });

    expect(mockGet).toHaveBeenCalledWith("/dashboard/summary");
    expect(screen.getByText("42")).toBeInTheDocument();
    expect(screen.getByText("$12500")).toBeInTheDocument();
    expect(screen.getByText("48")).toBeInTheDocument();
    expect(screen.getByText("3.2%")).toBeInTheDocument();
  });

  it("2. polls at 30s interval and updates data", async () => {
    await act(async () => {
      renderPage();
      await jest.runAllTimersAsync();
    });

    // Initial call
    expect(mockGet).toHaveBeenCalledTimes(1);

    // Update mock data for second poll
    const updatedSummary = { ...MOCK_SUMMARY, tasks_today_total: 50 };
    mockGet.mockResolvedValue(updatedSummary);

    // Advance 30s
    await act(async () => {
      jest.advanceTimersByTime(30000);
    });

    expect(mockGet).toHaveBeenCalledTimes(2);
    expect(screen.getByText("50")).toBeInTheDocument();
  });

  it("3. handles error state gracefully (silent failure)", async () => {
    mockGet.mockRejectedValue(new Error("Network error"));

    await act(async () => {
      renderPage();
      await jest.runAllTimersAsync();
    });

    // Dashboard doesn't show error UI — it stays at defaults (silent fail, 4 KPI cards show "—")
    const dashes = screen.getAllByText("—");
    expect(dashes.length).toBe(4);
  });

  it("4. renders child components (AlertBanner, HealthCard, AgentGrid, ActivityFeed)", async () => {
    await act(async () => {
      renderPage();
      await jest.runAllTimersAsync();
    });

    expect(screen.getByTestId("alert-banner")).toBeInTheDocument();
    expect(screen.getByTestId("health-card")).toBeInTheDocument();
    expect(screen.getByTestId("agent-grid")).toBeInTheDocument();
    expect(screen.getByTestId("activity-feed")).toBeInTheDocument();
  });
});
