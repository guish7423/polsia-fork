import "@testing-library/jest-dom";
import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import WorkflowsPage from "@/app/workflows/page";

// Mock next/navigation
const mockPush = jest.fn();
jest.mock("next/navigation", () => ({
  useRouter: () => ({ push: mockPush }),
  useParams: () => ({}),
}));

// Mock i18n
jest.mock("@/lib/i18n", () => ({
  useI18n: () => ({
    t: (key: string) => {
      const map: Record<string, string> = {
        "workflow.title": "Workflows",
      };
      return map[key] ?? key;
    },
    locale: "en",
    setLocale: () => {},
  }),
}));

// Mock API
const mockListWorkflows = jest.fn();
const mockCreateWorkflow = jest.fn();
const mockDeleteWorkflow = jest.fn();
const mockRunWorkflow = jest.fn();

jest.mock("@/lib/api", () => ({
  listWorkflows: (...args: unknown[]) => mockListWorkflows(...args),
  createWorkflow: (...args: unknown[]) => mockCreateWorkflow(...args),
  deleteWorkflow: (...args: unknown[]) => mockDeleteWorkflow(...args),
  runWorkflow: (...args: unknown[]) => mockRunWorkflow(...args),
  api: {
    get: jest.fn(),
    post: jest.fn(),
  },
  type: {},
}));

const MOCK_WORKFLOWS = [
  {
    id: 1,
    tenant_id: 1,
    name: "Customer Onboarding",
    description: "Onboard new customers with welcome email and setup tasks",
    nodes: [
      { id: "n1", type: "trigger" as const, position: { x: 0, y: 0 }, data: {} },
      { id: "n2", type: "agent" as const, position: { x: 200, y: 0 }, data: {} },
    ],
    edges: [{ id: "e1", source: "n1", target: "n2" }],
    is_active: true,
    created_at: "2026-06-01T10:00:00Z",
    updated_at: "2026-06-02T10:00:00Z",
  },
  {
    id: 2,
    tenant_id: 1,
    name: "Invoice Reminder",
    description: "Send reminders for overdue invoices",
    nodes: [
      { id: "n1", type: "trigger" as const, position: { x: 0, y: 0 }, data: {} },
    ],
    edges: [],
    is_active: false,
    created_at: "2026-05-15T08:00:00Z",
    updated_at: "2026-05-15T08:00:00Z",
  },
];

describe("WorkflowsPage", () => {
  beforeEach(() => {
    jest.clearAllMocks();
    mockListWorkflows.mockResolvedValue({
      items: MOCK_WORKFLOWS,
      total: 2,
    });
  });

  it("renders loading skeleton initially", () => {
    // Keep the promise pending so loading stays visible
    mockListWorkflows.mockImplementation(
      () => new Promise(() => {}),
    );
    render(<WorkflowsPage />);
    expect(screen.getByText("Loading...")).toBeInTheDocument();
  });

  it("renders empty state when no workflows exist", async () => {
    mockListWorkflows.mockResolvedValue({ items: [], total: 0 });
    render(<WorkflowsPage />);

    await waitFor(() => {
      expect(screen.getByText("No workflows yet")).toBeInTheDocument();
    });
  });

  it("renders workflow cards from API data", async () => {
    render(<WorkflowsPage />);

    await waitFor(() => {
      expect(
        screen.getByText("Customer Onboarding"),
      ).toBeInTheDocument();
    });

    expect(screen.getByText("Invoice Reminder")).toBeInTheDocument();
    expect(screen.getByText("active")).toBeInTheDocument();
    expect(screen.getByText("inactive")).toBeInTheDocument();
    expect(screen.getByText("2 nodes")).toBeInTheDocument();
    expect(screen.getByText("1 node")).toBeInTheDocument();
  });

  it("opens create dialog and creates a workflow", async () => {
    mockCreateWorkflow.mockResolvedValue({ id: 3, name: "New WF" });

    render(<WorkflowsPage />);

    // Click Create button
    const createBtn = screen.getByText("Create Workflow");
    await userEvent.click(createBtn);

    // Form should appear
    const nameInput = screen.getByPlaceholderText("My workflow");
    await userEvent.type(nameInput, "New WF");
    const descInput = screen.getByPlaceholderText("What this workflow does");
    await userEvent.type(descInput, "Test description");

    // Submit — find the exact "Create" submit button (not "Create Workflow")
    const submitBtn = screen.getByRole("button", { name: "Create" });
    await userEvent.click(submitBtn);

    await waitFor(() => {
      expect(mockCreateWorkflow).toHaveBeenCalledWith({
        name: "New WF",
        description: "Test description",
      });
    });
  });

  it("shows confirm modal before deleting a workflow", async () => {
    mockDeleteWorkflow.mockResolvedValue(undefined);

    render(<WorkflowsPage />);

    await waitFor(() => {
      expect(screen.getByText("Customer Onboarding")).toBeInTheDocument();
    });

    // Click Delete on the first workflow card
    const deleteButtons = screen.getAllByText("Delete");
    await userEvent.click(deleteButtons[0]);

    // Modal should appear with title "Delete Workflow"
    await waitFor(() => {
      expect(
        screen.getByText("Delete Workflow"),
      ).toBeInTheDocument();
    });

    // Click the modal's Delete button (last one — after card buttons)
    const allDeleteBtns = screen.getAllByRole("button", { name: "Delete" });
    await userEvent.click(allDeleteBtns[allDeleteBtns.length - 1]);

    await waitFor(() => {
      expect(mockDeleteWorkflow).toHaveBeenCalledWith(1);
    });
  });

  it("renders error state when API fails", async () => {
    mockListWorkflows.mockRejectedValue(new Error("Network error"));

    render(<WorkflowsPage />);

    await waitFor(() => {
      expect(screen.getByText("Network error")).toBeInTheDocument();
    });
  });
});
