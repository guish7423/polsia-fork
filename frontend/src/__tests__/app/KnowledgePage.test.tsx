import "@testing-library/jest-dom";
import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import KnowledgePage from "@/app/knowledge/page";

// Mock next/navigation
jest.mock("next/navigation", () => ({
  useRouter: () => ({ replace: jest.fn() }),
  usePathname: () => "/knowledge",
}));

// Mock i18n
jest.mock("@/lib/i18n", () => ({
  useI18n: () => ({
    t: (key: string) => {
      const map: Record<string, string> = {
        "knowledge.title": "Knowledge Base",
        "knowledge.upload": "Upload",
        "knowledge.uploading": "Uploading…",
        "knowledge.search": "Semantic Search",
        "knowledge.searching": "Searching…",
        "knowledge.filename": "Filename",
        "knowledge.type": "Type",
        "knowledge.status": "Status",
        "knowledge.chunks": "Chunks",
        "knowledge.date": "Upload Date",
        "knowledge.delete": "Delete",
        "knowledge.deleting": "Deleting…",
        "knowledge.empty": "No documents yet. Drag & drop or click to upload.",
        "knowledge.no_results": "No matching results",
        "knowledge.drop_hint": "Drop files here or click to browse",
        "knowledge.status_uploading": "Uploading",
        "knowledge.status_ready": "Ready",
        "knowledge.status_error": "Error",
        "knowledge.search_placeholder": "Type to search…",
        "knowledge.drag_active": "Release to upload",
        "knowledge.delete_confirm": "Confirm Delete",
        "knowledge.delete_confirm_body":
          'Are you sure you want to delete "{name}"? This cannot be undone.',
        "knowledge.cancel": "Cancel",
        "knowledge.confirm": "Confirm",
        "knowledge.error_prefix": "Error",
        "knowledge.snippet": "Snippet",
        "knowledge.score": "Relevance",
      };
      return map[key] ?? key;
    },
    locale: "en",
    setLocale: () => {},
  }),
}));

// Mock api functions
const mockListDocuments = jest.fn();
const mockUploadDocument = jest.fn();
const mockDeleteDocument = jest.fn();
const mockSemanticSearch = jest.fn();

jest.mock("@/lib/api", () => ({
  listKnowledgeDocuments: (...args: unknown[]) => mockListDocuments(...args),
  uploadKnowledgeDocument: (...args: unknown[]) => mockUploadDocument(...args),
  deleteKnowledgeDocument: (...args: unknown[]) => mockDeleteDocument(...args),
  semanticSearchKnowledge: (...args: unknown[]) => mockSemanticSearch(...args),
}));

const MOCK_DOCUMENTS = [
  {
    id: 1,
    filename: "report.pdf",
    file_type: "pdf",
    status: "ready" as const,
    chunk_count: 12,
    error_message: null,
    created_at: "2026-06-01T10:00:00Z",
  },
  {
    id: 2,
    filename: "notes.txt",
    file_type: "txt",
    status: "uploading" as const,
    chunk_count: 0,
    error_message: null,
    created_at: "2026-06-02T10:00:00Z",
  },
  {
    id: 3,
    filename: "broken.csv",
    file_type: "csv",
    status: "error" as const,
    chunk_count: 0,
    error_message: "Parsing failed",
    created_at: "2026-06-03T10:00:00Z",
  },
];

describe("KnowledgePage", () => {
  beforeEach(() => {
    jest.clearAllMocks();
    mockListDocuments.mockResolvedValue({
      documents: MOCK_DOCUMENTS,
      total: 3,
    });
  });

  it("renders the page title", async () => {
    render(<KnowledgePage />);
    expect(await screen.findByText("Knowledge Base")).toBeInTheDocument();
  });

  it("renders the drag-and-drop upload zone", async () => {
    render(<KnowledgePage />);
    expect(
      await screen.findByText("Drop files here or click to browse"),
    ).toBeInTheDocument();
  });

  it("renders document rows from API data", async () => {
    render(<KnowledgePage />);

    await waitFor(() => {
      expect(screen.getByText("report.pdf")).toBeInTheDocument();
    });

    expect(screen.getByText("notes.txt")).toBeInTheDocument();
    expect(screen.getByText("broken.csv")).toBeInTheDocument();
  });

  it("renders three status badges (ready/uploading/error)", async () => {
    render(<KnowledgePage />);

    await waitFor(() => {
      expect(screen.getByText("Ready")).toBeInTheDocument();
    });

    expect(screen.getByText("Uploading")).toBeInTheDocument();
    expect(screen.getByText("Error")).toBeInTheDocument();
  });

  it("shows confirm dialog before deleting a document", async () => {
    render(<KnowledgePage />);

    await waitFor(() => {
      expect(screen.getByText("report.pdf")).toBeInTheDocument();
    });

    const deleteButtons = screen.getAllByText("Delete");
    await userEvent.click(deleteButtons[0]);

    // Confirm dialog should appear
    expect(screen.getByText("Confirm Delete")).toBeInTheDocument();
    expect(
      screen.getByText(
        'Are you sure you want to delete "report.pdf"? This cannot be undone.',
      ),
    ).toBeInTheDocument();
  });

  it("calls deleteKnowledgeDocument after confirmation", async () => {
    mockDeleteDocument.mockResolvedValue(undefined);

    render(<KnowledgePage />);

    await waitFor(() => {
      expect(screen.getByText("report.pdf")).toBeInTheDocument();
    });

    const deleteButtons = screen.getAllByText("Delete");
    await userEvent.click(deleteButtons[0]);

    const confirmButton = screen.getByText("Confirm");
    await userEvent.click(confirmButton);

    await waitFor(() => {
      expect(mockDeleteDocument).toHaveBeenCalledWith(1);
    });
  });

  it("switches to search view and performs semantic search", async () => {
    mockSemanticSearch.mockResolvedValue([
      {
        id: 1,
        filename: "report.pdf",
        file_type: "pdf",
        snippet: "AI agents are transforming business operations.",
        score: 0.92,
        chunk_index: 3,
      },
    ]);

    render(<KnowledgePage />);

    // Switch to search view — click the view toggle button
    const toggleButtons = await screen.findAllByText("Semantic Search");
    // First is the view toggle in header, second is the execute button
    // Both say "Semantic Search" in search view; click the toggle to enter search
    await userEvent.click(toggleButtons[0]);

    // Type query and search — click the execute button (the second one)
    const input = screen.getByPlaceholderText("Type to search…");
    await userEvent.type(input, "AI agents");

    const searchBtns = screen.getAllByText("Semantic Search");
    await userEvent.click(searchBtns[1]);

    await waitFor(() => {
      expect(mockSemanticSearch).toHaveBeenCalledWith("AI agents");
    });

    await waitFor(() => {
      expect(
        screen.getByText(/AI agents are transforming/),
      ).toBeInTheDocument();
    });
  });
});
