import "@testing-library/jest-dom";
import { render, screen } from "@testing-library/react";
import { PageTitle, SectionTitle, Text } from "@/components/PageTitle";

const mockT = jest.fn();
jest.mock("@/lib/i18n", () => ({
  useI18n: () => ({ t: mockT }),
}));

describe("PageTitle", () => {
  beforeEach(() => {
    mockT.mockReset();
  });

  it("renders translated text from i18nKey", () => {
    mockT.mockReturnValue("Dashboard");
    render(<PageTitle i18nKey="dash.title" />);
    expect(screen.getByText("Dashboard")).toBeInTheDocument();
  });

  it("renders as h1 with correct classes", () => {
    mockT.mockReturnValue("Agents");
    render(<PageTitle i18nKey="agents.title" />);
    const h1 = screen.getByRole("heading", { level: 1 });
    expect(h1).toHaveClass("text-2xl", "font-bold", "text-white");
  });
});

describe("SectionTitle", () => {
  beforeEach(() => {
    mockT.mockReset();
  });

  it("renders translated text from i18nKey", () => {
    mockT.mockReturnValue("Agent Status");
    render(<SectionTitle i18nKey="dash.agent_status" />);
    expect(screen.getByText("Agent Status")).toBeInTheDocument();
  });

  it("renders as h2 with uppercase tracking classes", () => {
    mockT.mockReturnValue("Live Activity");
    render(<SectionTitle i18nKey="dash.live_activity" />);
    const h2 = screen.getByRole("heading", { level: 2 });
    expect(h2).toHaveClass("uppercase", "tracking-wider");
  });
});

describe("Text", () => {
  beforeEach(() => {
    mockT.mockReset();
  });

  it("renders translated text as fragment", () => {
    mockT.mockReturnValue("No tasks yet.");
    const { container } = render(<span><Text i18nKey="tasks.empty" /></span>);
    expect(container).toHaveTextContent("No tasks yet.");
  });

  it("calls t with the correct key", () => {
    mockT.mockReturnValue("Completed");
    render(<Text i18nKey="status.completed" />);
    expect(mockT).toHaveBeenCalledWith("status.completed");
  });
});
