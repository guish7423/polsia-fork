import "@testing-library/jest-dom";
import { render, screen, act } from "@testing-library/react";
import { SystemHealthCard } from "@/components/dashboard/SystemHealthCard";
import { I18nProvider } from "@/lib/i18n";
import { api } from "@/lib/api";
import type { DashboardHealth } from "@/lib/api";

// ─── Mock api.get ───────────────────────────────────────────────────────────

const mockGet = jest.spyOn(api, "get") as jest.Mock;

function renderWithProvider(ui: React.ReactElement) {
  return render(<I18nProvider>{ui}</I18nProvider>);
}

beforeEach(() => {
  jest.useFakeTimers();
  mockGet.mockReset();
});

afterEach(() => {
  jest.useRealTimers();
});

const HEALTHY_RESPONSE: DashboardHealth = {
  overall: "healthy",
  checks: {
    agents: { status: "healthy", running: 5, errored: 0, total: 8 },
    tasks: { status: "healthy", pending: 3, failed_24h: 1, total: 120 },
    quota: { status: "healthy", avg_usage_pct: 45, exceeded: [] },
    cost: { status: "healthy", cost_24h_usd: 12.34, budget_pct: 30 },
    last_updated: "2026-06-04T12:00:00Z",
  },
};

const DEGRADED_RESPONSE: DashboardHealth = {
  overall: "degraded",
  checks: {
    agents: { status: "degraded", running: 3, errored: 2, total: 8 },
    tasks: { status: "degraded", pending: 10, failed_24h: 7, total: 120 },
    quota: { status: "degraded", avg_usage_pct: 92, exceeded: ["cost"] },
    cost: { status: "warning", cost_24h_usd: 45.67, budget_pct: 85 },
    last_updated: "2026-06-04T12:00:00Z",
  },
};

// ─── Tests ──────────────────────────────────────────────────────────────────

describe("SystemHealthCard", () => {
  it('shows "All Systems Operational" when healthy', async () => {
    mockGet.mockResolvedValue(HEALTHY_RESPONSE);

    await act(async () => {
      renderWithProvider(<SystemHealthCard />);
      await jest.runAllTimersAsync();
    });

    expect(screen.getByText("All Systems Operational")).toBeInTheDocument();
    // Green dot indicator
    const dot = screen.getByTestId("health-dot");
    expect(dot.className).toMatch(/green/i);
  });

  it('shows "System Degraded" when degraded', async () => {
    mockGet.mockResolvedValue(DEGRADED_RESPONSE);

    await act(async () => {
      renderWithProvider(<SystemHealthCard />);
      await jest.runAllTimersAsync();
    });

    expect(screen.getByText("System Degraded")).toBeInTheDocument();
    const dot = screen.getByTestId("health-dot");
    expect(dot.className).toMatch(/yellow/i);
  });

  it("displays individual check items with status indicators", async () => {
    mockGet.mockResolvedValue(HEALTHY_RESPONSE);

    await act(async () => {
      renderWithProvider(<SystemHealthCard />);
      await jest.runAllTimersAsync();
    });

    // Should show all check sections
    expect(screen.getByText("Agents")).toBeInTheDocument();
    expect(screen.getByText("Tasks")).toBeInTheDocument();
    expect(screen.getByText("Quota")).toBeInTheDocument();
    expect(screen.getByText("Cost")).toBeInTheDocument();
    expect(screen.getByText(/Last Updated/i)).toBeInTheDocument();
  });

  it("falls back gracefully when fetch fails", async () => {
    mockGet.mockRejectedValue(new Error("Network error"));

    await act(async () => {
      renderWithProvider(<SystemHealthCard />);
      await jest.runAllTimersAsync();
    });

    // Should show degraded state on error
    expect(screen.getByText("System Degraded")).toBeInTheDocument();
  });
});
