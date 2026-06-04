import "@testing-library/jest-dom";
import { render, screen, act } from "@testing-library/react";
import { GlobalAlertBanner } from "@/components/dashboard/GlobalAlertBanner";
import { I18nProvider } from "@/lib/i18n";
import { api } from "@/lib/api";
import type { ActiveAlertsResponse } from "@/lib/api";

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

function mockAlertsResponse(alerts: ActiveAlertsResponse["alerts"]) {
  mockGet.mockResolvedValue({ alerts, total: alerts.length });
}

// ─── Tests ──────────────────────────────────────────────────────────────────

describe("GlobalAlertBanner", () => {
  it("renders nothing when there are no active alerts", async () => {
    mockAlertsResponse([]);

    await act(async () => {
      renderWithProvider(<GlobalAlertBanner />);
      await jest.runAllTimersAsync();
    });

    expect(screen.queryByRole("alert")).not.toBeInTheDocument();
  });

  it("shows a red critical banner with dismiss button for critical alerts", async () => {
    mockAlertsResponse([
      {
        id: 1,
        tenant_id: 1,
        alert_type: "agent_error",
        severity: "critical",
        message: "Agent orchestrator has failed 3 times",
        source: "orchestrator",
        status: "pending",
        metadata_json: null,
        created_at: new Date().toISOString(),
        resolved_at: null,
      },
    ]);

    await act(async () => {
      renderWithProvider(<GlobalAlertBanner />);
      await jest.runAllTimersAsync();
    });

    expect(screen.getByText("Agent orchestrator has failed 3 times")).toBeInTheDocument();
    expect(screen.getByText("Dismiss")).toBeInTheDocument();
    // Banner should have red styling
    const banner = screen.getByRole("alert");
    expect(banner.className).toMatch(/red|bg-red/i);
  });

  it("shows a yellow banner for warning severity", async () => {
    mockAlertsResponse([
      {
        id: 2,
        tenant_id: 1,
        alert_type: "quota_warning",
        severity: "warning",
        message: "Quota usage at 94.2%",
        source: "tasks",
        status: "pending",
        metadata_json: null,
        created_at: new Date().toISOString(),
        resolved_at: null,
      },
    ]);

    await act(async () => {
      renderWithProvider(<GlobalAlertBanner />);
      await jest.runAllTimersAsync();
    });

    expect(screen.getByText("Quota usage at 94.2%")).toBeInTheDocument();
    const banner = screen.getByRole("alert");
    expect(banner.className).toMatch(/yellow|bg-yellow/i);
  });

  it("shows a multi-alert count when there are 3+ unresolved alerts", async () => {
    const alerts = Array.from({ length: 3 }, (_, i) => ({
      id: i + 1,
      tenant_id: 1,
      alert_type: "agent_error",
      severity: "critical" as const,
      message: `Error ${i + 1}`,
      source: "agent",
      status: "pending",
      metadata_json: null,
      created_at: new Date().toISOString(),
      resolved_at: null,
    }));
    mockAlertsResponse(alerts);

    await act(async () => {
      renderWithProvider(<GlobalAlertBanner />);
      await jest.runAllTimersAsync();
    });

    expect(screen.getByText("3 unresolved alerts")).toBeInTheDocument();
    expect(screen.getByText("Dismiss")).toBeInTheDocument();
  });
});
