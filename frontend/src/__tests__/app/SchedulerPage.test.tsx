import "@testing-library/jest-dom";
import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import SchedulerPage from "@/app/scheduler/page";

// Mock next/navigation
jest.mock("next/navigation", () => ({
  useRouter: () => ({ replace: jest.fn() }),
  usePathname: () => "/scheduler",
}));

// Mock I18n so PageTitle translates keys
jest.mock("@/lib/i18n", () => ({
  useI18n: () => ({
    t: (key: string) => {
      const map: Record<string, string> = {
        "scheduler.title": "Scheduler Status",
        "scheduler.running": "Running",
        "scheduler.pending": "Pending",
        "scheduler.queued": "Queued",
        "scheduler.load_score": "Load Score",
        "scheduler.rebalance": "Rebalance",
        "scheduler.rebalancing": "Rebalancing…",
      };
      return map[key] ?? key;
    },
    locale: "en",
    setLocale: () => {},
  }),
}));

// Mock api
const mockApiGet = jest.fn();
jest.mock("@/lib/api", () => ({
  api: {
    get: (...args: unknown[]) => mockApiGet(...args),
    post: jest.fn().mockResolvedValue({ message: "Rebalanced" }),
  },
  type: {},
}));

import { api } from "@/lib/api";

const MOCK_STATUS = {
  tenant_id: 1,
  running: 3,
  pending: 7,
  queued: 2,
  load_score: 68,
  agents_limit: 10,
  threshold_exceeded: false,
};

describe("SchedulerPage", () => {
  beforeEach(() => {
    jest.clearAllMocks();
    mockApiGet.mockResolvedValue(MOCK_STATUS);
  });

  it("renders the page title", async () => {
    render(<SchedulerPage />);
    expect(await screen.findByText("Scheduler Status")).toBeInTheDocument();
  });

  it("renders load metric cards from API data", async () => {
    render(<SchedulerPage />);

    await waitFor(() => {
      expect(screen.getByText("3")).toBeInTheDocument();
    });

    expect(screen.getByText("7")).toBeInTheDocument();
    expect(screen.getByText("2")).toBeInTheDocument();
    expect(screen.getByText("68%")).toBeInTheDocument();
  });

  it("shows the rebalance button", async () => {
    render(<SchedulerPage />);

    const btn = await screen.findByRole("button", { name: /rebalance/i });
    expect(btn).toBeInTheDocument();
    expect(btn).not.toBeDisabled();
  });

  it("disables rebalance button while rebalancing", async () => {
    (api.post as jest.Mock).mockImplementation(
      () => new Promise(() => {}), // never resolves to keep rebalancing state
    );

    render(<SchedulerPage />);

    const btn = await screen.findByRole("button", { name: /rebalance/i });
    await userEvent.click(btn);

    expect(btn).toBeDisabled();
    expect(btn).toHaveTextContent(/rebalancing/i);
  });

  it("shows threshold warning when threshold_exceeded is true", async () => {
    mockApiGet.mockResolvedValue({ ...MOCK_STATUS, threshold_exceeded: true });

    render(<SchedulerPage />);

    await waitFor(() => {
      // "threshold exceeded" appears in both the banner and the card subtitle
      const els = screen.getAllByText(/threshold exceeded/i);
      expect(els.length).toBeGreaterThanOrEqual(1);
    });
  });

  it("calls API POST /scheduler/rebalance on button click", async () => {
    const postMock = api.post as jest.Mock;
    postMock.mockResolvedValue({ message: "Rebalanced" });

    render(<SchedulerPage />);

    const btn = await screen.findByRole("button", { name: /rebalance/i });
    await userEvent.click(btn);

    await waitFor(() => {
      expect(postMock).toHaveBeenCalledWith("/scheduler/rebalance");
    });
  });
});
