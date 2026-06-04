import "@testing-library/jest-dom";
import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import MarketplacePage from "@/app/marketplace/page";

// Mock i18n
const mockT = jest.fn((key: string) => {
  const map: Record<string, string> = {
    "marketplace.title": "Agent Marketplace",
    "marketplace.search": "Search agents…",
    "marketplace.install": "Install",
    "marketplace.installed": "Installed",
    "marketplace.uninstall": "Uninstall",
    "marketplace.empty": "No agents available.",
  };
  return map[key] ?? key;
});
jest.mock("@/lib/i18n", () => ({
  useI18n: () => ({ t: mockT, locale: "en", setLocale: jest.fn() }),
}));

// Mock api
const mockApiGet = jest.fn();
const mockApiPost = jest.fn();
jest.mock("@/lib/api", () => ({
  api: {
    get: (...args: unknown[]) => mockApiGet(...args),
    post: (...args: unknown[]) => mockApiPost(...args),
  },
}));

const makeAgent = (overrides: Record<string, unknown>) => ({
  name: "orchestrator",
  type: "system",
  description: "Daily planning and agent coordination",
  installed: false,
  version: "1.0.0",
  ...overrides,
});

const mockAgents = [
  makeAgent({
    name: "orchestrator",
    description: "Daily planning and agent coordination",
  }),
  makeAgent({
    name: "social_media",
    type: "marketing",
    description: "Social media management",
    installed: true,
  }),
  makeAgent({
    name: "finance",
    type: "accounting",
    description: "Financial tracking",
  }),
];

describe("MarketplacePage", () => {
  beforeEach(() => {
    jest.clearAllMocks();
  });

  it("shows loading skeletons while data is loading", () => {
    mockApiGet.mockReturnValue(new Promise(() => {})); // never resolves
    const { container } = render(<MarketplacePage />);
    expect(container.querySelectorAll(".animate-pulse").length).toBe(6);
  });

  it("shows empty state when no agents", async () => {
    mockApiGet.mockResolvedValue([]);
    render(<MarketplacePage />);
    await waitFor(() => {
      expect(screen.getByText("No agents available.")).toBeInTheDocument();
    });
  });

  it("renders agent cards when loaded", async () => {
    mockApiGet.mockResolvedValue(mockAgents);
    render(<MarketplacePage />);
    await waitFor(() => {
      expect(screen.getByText("orchestrator")).toBeInTheDocument();
      expect(screen.getByText("social_media")).toBeInTheDocument();
      expect(screen.getByText("finance")).toBeInTheDocument();
    });
  });

  it("shows Install button for uninstalled agents", async () => {
    mockApiGet.mockResolvedValue(mockAgents);
    render(<MarketplacePage />);
    await waitFor(() => {
      const installBtns = screen.getAllByText("Install");
      // orchestrator + finance (2 uninstalled)
      expect(installBtns).toHaveLength(2);
    });
  });

  it("shows Uninstall button for installed agents", async () => {
    mockApiGet.mockResolvedValue(mockAgents);
    render(<MarketplacePage />);
    await waitFor(() => {
      expect(screen.getByText("Uninstall")).toBeInTheDocument();
    });
  });

  it("calls install API when Install is clicked", async () => {
    mockApiGet.mockResolvedValue(mockAgents);
    mockApiPost.mockResolvedValue({});
    render(<MarketplacePage />);
    await waitFor(() => screen.getByText("orchestrator"));

    const user = userEvent.setup();
    const installBtn = screen.getAllByText("Install")[0];
    await user.click(installBtn);

    await waitFor(() => {
      expect(mockApiPost).toHaveBeenCalledWith(
        "/marketplace/agents/orchestrator/install"
      );
    });
  });

  it("calls uninstall API when Uninstall is clicked", async () => {
    mockApiGet.mockResolvedValue(mockAgents);
    mockApiPost.mockResolvedValue({});
    render(<MarketplacePage />);
    await waitFor(() => screen.getByText("social_media"));

    const user = userEvent.setup();
    await user.click(screen.getByText("Uninstall"));

    await waitFor(() => {
      expect(mockApiPost).toHaveBeenCalledWith(
        "/marketplace/agents/social_media/uninstall"
      );
    });
  });

  it("filters agents by search query", async () => {
    mockApiGet.mockResolvedValue(mockAgents);
    render(<MarketplacePage />);
    await waitFor(() => screen.getByText("orchestrator"));

    const user = userEvent.setup();
    const searchInput = screen.getByPlaceholderText("Search agents…");
    await user.type(searchInput, "finance");

    await waitFor(() => {
      expect(screen.getByText("finance")).toBeInTheDocument();
      expect(screen.queryByText("orchestrator")).not.toBeInTheDocument();
      expect(screen.queryByText("social_media")).not.toBeInTheDocument();
    });
  });
});
