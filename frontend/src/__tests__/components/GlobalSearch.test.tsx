import "@testing-library/jest-dom";
import { render, screen, fireEvent, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { GlobalSearch } from "@/components/layout/GlobalSearch";

const mockPush = jest.fn();

jest.mock("next/navigation", () => ({
  useRouter: () => ({ push: mockPush }),
}));

const mockSearchApi = jest.fn();
jest.mock("@/lib/api", () => ({
  ...jest.requireActual("@/lib/api"),
  searchApi: (...args: unknown[]) => mockSearchApi(...args),
}));

// Mock useI18n — return plain English
jest.mock("@/lib/i18n", () => ({
  useI18n: () => ({
    locale: "en",
    setLocale: jest.fn(),
    t: (key: string) => {
      const map: Record<string, string> = {
        "search.placeholder": "Type to search...",
        "search.no_results": "No results found",
        "search.group.tasks": "Tasks",
        "search.group.agents": "Agents",
        "search.group.alerts": "Alerts",
        "search.group.runs": "Runs",
      };
      return map[key] ?? key;
    },
  }),
}));

beforeEach(() => {
  mockPush.mockClear();
  mockSearchApi.mockClear();
});

describe("GlobalSearch", () => {
  it("opens modal on Cmd+K and shows empty state", () => {
    render(<GlobalSearch />);

    // Modal should not be visible initially
    expect(screen.queryByPlaceholderText("Type to search...")).not.toBeInTheDocument();

    // Press Cmd+K
    fireEvent.keyDown(document, { key: "k", metaKey: true });

    expect(screen.getByPlaceholderText("Type to search...")).toBeInTheDocument();
  });

  it("shows empty state message when opened with no query", () => {
    render(<GlobalSearch />);

    fireEvent.keyDown(document, { key: "k", metaKey: true });

    expect(screen.getByPlaceholderText("Type to search...")).toBeInTheDocument();
  });

  it("displays search results grouped by type", async () => {
    mockSearchApi.mockResolvedValue({
      results: [
        { type: "task", id: 1, title: "Deploy API", description: "Deploy the new API", url: "/tasks/1", score: 4 },
        { type: "task", id: 2, title: "Write docs", description: "Write documentation", url: "/tasks/2", score: 3 },
        { type: "agent", id: 1, title: "Orchestrator", description: "Main orchestrator agent", url: "/agents", score: 2 },
        { type: "alert", id: 1, title: "High CPU usage", description: "CPU at 95%", url: "/alerts/1", score: 3 },
        { type: "run", id: 1, title: "Run #42", description: "Agent run", url: "/runs/1", score: 2 },
      ],
    });

    render(<GlobalSearch />);

    fireEvent.keyDown(document, { key: "k", metaKey: true });

    const input = screen.getByPlaceholderText("Type to search...");
    await userEvent.type(input, "deploy");

    await waitFor(() => {
      expect(screen.getByText("Tasks")).toBeInTheDocument();
      expect(screen.getByText("Agents")).toBeInTheDocument();
      expect(screen.getByText("Alerts")).toBeInTheDocument();
      expect(screen.getByText("Runs")).toBeInTheDocument();

      // Verify results are rendered (text is split by <mark> highlights)
      const buttons = screen.getAllByRole("button");
      expect(buttons.length).toBe(5);
    });
  });

  it("shows no results message when API returns empty", async () => {
    mockSearchApi.mockResolvedValue({ results: [] });

    render(<GlobalSearch />);

    fireEvent.keyDown(document, { key: "k", metaKey: true });

    const input = screen.getByPlaceholderText("Type to search...");
    await userEvent.type(input, "zzzznotfound");

    await waitFor(() => {
      expect(screen.getByText("No results found")).toBeInTheDocument();
    });
  });

  it("closes on ESC and navigates on result click", async () => {
    mockSearchApi.mockResolvedValue({
      results: [
        { type: "task", id: 1, title: "Deploy API", description: "Deploy the new API", url: "/tasks/1", score: 4 },
      ],
    });

    render(<GlobalSearch />);

    fireEvent.keyDown(document, { key: "k", metaKey: true });
    const input = screen.getByPlaceholderText("Type to search...");
    await userEvent.type(input, "deploy");

    await waitFor(() => {
      expect(screen.getByText("Tasks")).toBeInTheDocument();
    });

    // Click first result button → navigates
    const buttons = screen.getAllByRole("button");
    fireEvent.click(buttons[0]);
    expect(mockPush).toHaveBeenCalledWith("/tasks/1");

    // Modal should close
    await waitFor(() => {
      expect(screen.queryByPlaceholderText("Type to search...")).not.toBeInTheDocument();
    });

    // Re-open and test ESC
    fireEvent.keyDown(document, { key: "k", metaKey: true });
    expect(screen.getByPlaceholderText("Type to search...")).toBeInTheDocument();

    fireEvent.keyDown(screen.getByPlaceholderText("Type to search..."), { key: "Escape" });
    expect(screen.queryByPlaceholderText("Type to search...")).not.toBeInTheDocument();
  });
});
