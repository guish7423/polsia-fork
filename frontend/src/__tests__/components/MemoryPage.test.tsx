import "@testing-library/jest-dom";
import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import MemoryPage from "@/app/memory/page";

// Mock i18n
const mockT = jest.fn();
jest.mock("@/lib/i18n", () => ({
  useI18n: () => ({ t: mockT }),
}));

// Mock api.get
jest.mock("@/lib/api", () => ({
  api: { get: jest.fn() },
}));

import { api } from "@/lib/api";
const mockApiGet = api.get as jest.Mock;

const mockMemories = [
  { id: 1, category: "insight", title: "Customer preference shift", content: "Users prefer async communication over real-time chat.", created_at: "2026-05-30T10:00:00Z" },
  { id: 2, category: "strategy", title: "Q3 pricing analysis", content: "Competitor analysis shows room for 15% price increase.", created_at: "2026-05-29T14:00:00Z" },
];

describe("MemoryPage", () => {
  beforeEach(() => {
    jest.clearAllMocks();
    mockT.mockImplementation((key: string) => {
      const map: Record<string, string> = {
        "memory.title": "Memory",
        "memory.search": "Search",
        "memory.searching": "Searching…",
        "memory.no_results": "No matching results",
        "memory.category": "Category",
      };
      return map[key] ?? key;
    });
  });

  it("renders the page title", () => {
    mockApiGet.mockResolvedValue([]);
    render(<MemoryPage />);
    expect(screen.getByText("Memory")).toBeInTheDocument();
  });

  it("shows a search input and button", () => {
    mockApiGet.mockResolvedValue([]);
    render(<MemoryPage />);
    expect(screen.getByPlaceholderText("Category...")).toBeInTheDocument();
    expect(screen.getByText("Search")).toBeInTheDocument();
  });

  it("displays search results after searching", async () => {
    mockApiGet.mockResolvedValue(mockMemories);

    render(<MemoryPage />);
    const user = userEvent.setup();

    const input = screen.getByPlaceholderText("Category...");
    await user.type(input, "insight");
    await user.click(screen.getByText("Search"));

    await waitFor(() => {
      expect(screen.getByText("Customer preference shift")).toBeInTheDocument();
    });

    expect(screen.getByText("insight")).toBeInTheDocument();
    expect(screen.getByText(/Users prefer async/)).toBeInTheDocument();
  });

  it("shows 'no results' message when search returns empty", async () => {
    mockApiGet.mockResolvedValue([]);

    render(<MemoryPage />);
    const user = userEvent.setup();

    await user.type(screen.getByPlaceholderText("Category..."), "nonexistent");
    await user.click(screen.getByText("Search"));

    await waitFor(() => {
      expect(screen.getByText("No matching results")).toBeInTheDocument();
    });
  });

  it("triggers search on Enter key", async () => {
    mockApiGet.mockResolvedValue(mockMemories);

    render(<MemoryPage />);
    const user = userEvent.setup();

    const input = screen.getByPlaceholderText("Category...");
    await user.type(input, "pricing{Enter}");

    await waitFor(() => {
      expect(screen.getByText("Q3 pricing analysis")).toBeInTheDocument();
    });
  });

  it("disables search button while loading", async () => {
    // Return a promise that never resolves during the check
    mockApiGet.mockImplementation(() => new Promise(() => {}));

    render(<MemoryPage />);
    const user = userEvent.setup();

    await user.type(screen.getByPlaceholderText("Category..."), "test");
    await user.click(screen.getByText("Search"));

    // Button text should change to "Searching…"
    expect(screen.getByText("Searching…")).toBeDisabled();
  });

  it("does not search with empty query", async () => {
    render(<MemoryPage />);
    const user = userEvent.setup();

    await user.click(screen.getByText("Search"));
    expect(mockApiGet).not.toHaveBeenCalled();
  });
});
