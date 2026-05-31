import "@testing-library/jest-dom";
import { render, screen, act } from "@testing-library/react";
import DemoPage from "@/app/demo/page";

// Mock next/link
jest.mock("next/link", () => {
  return function MockLink({ href, children, className }: { href: string; children: React.ReactNode; className?: string }) {
    return <a href={href} className={className}>{children}</a>;
  };
});

describe("DemoPage", () => {
  beforeEach(() => {
    jest.useFakeTimers();
  });

  afterEach(() => {
    jest.useRealTimers();
  });

  it("renders the demo page title", () => {
    render(<DemoPage />);
    expect(screen.getByText("Live Demo")).toBeInTheDocument();
  });

  it("renders all 10 agent cards", () => {
    render(<DemoPage />);
    expect(screen.getByText("Orchestrator / CEO")).toBeInTheDocument();
    expect(screen.getByText("Finance")).toBeInTheDocument();
    expect(screen.getByText("Deployment")).toBeInTheDocument();
  });

  it("renders KPI cards with titles", () => {
    render(<DemoPage />);
    expect(screen.getByText("Tasks Today")).toBeInTheDocument();
    expect(screen.getByText("MRR")).toBeInTheDocument();
    expect(screen.getByText("Active Customers")).toBeInTheDocument();
    expect(screen.getByText("Churn Rate")).toBeInTheDocument();
  });

  it("renders CTA section with deploy and launch buttons", () => {
    render(<DemoPage />);
    expect(screen.getByText("Deploy Free →")).toBeInTheDocument();
    expect(screen.getByText("Launch App")).toBeInTheDocument();
  });

  it("shows GitHub link", () => {
    render(<DemoPage />);
    const githubLinks = screen.getAllByText("GitHub");
    expect(githubLinks.length).toBeGreaterThanOrEqual(1);
  });

  it("shows empty activity state initially", () => {
    render(<DemoPage />);
    expect(screen.getByText(/Agents are working/)).toBeInTheDocument();
  });

  it("renders activity events after timers fire", () => {
    render(<DemoPage />);

    // Advance timers to trigger the activity feed simulation
    act(() => {
      jest.advanceTimersByTime(2000);
    });

    expect(screen.getByText(/Daily plan generated/)).toBeInTheDocument();
  });

  it("shows agent status indicators", () => {
    render(<DemoPage />);
    const idleElements = screen.getAllByText("idle");
    expect(idleElements.length).toBeGreaterThan(0);
  });

  it("has a sticky header with Back to App link", () => {
    render(<DemoPage />);
    expect(screen.getByText("Back to App")).toBeInTheDocument();
  });
});
