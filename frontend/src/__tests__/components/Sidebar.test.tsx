import "@testing-library/jest-dom";
import { render, screen } from "@testing-library/react";
import { Sidebar } from "@/components/layout/Sidebar";

// Mock next/navigation
jest.mock("next/navigation", () => ({
  usePathname: () => "/dashboard",
  useRouter: () => ({ push: jest.fn() }),
}));

// Mock next/link
jest.mock("next/link", () => {
  return function MockLink({ href, children, className }: { href: string; children: React.ReactNode; className?: string }) {
    return <a href={href} className={className}>{children}</a>;
  };
});

// Mock i18n — return plain English for nav keys
jest.mock("@/lib/i18n", () => ({
  useI18n: () => ({
    locale: "en",
    setLocale: jest.fn(),
    t: (key: string) => {
      const map: Record<string, string> = {
        "nav.dashboard": "Dashboard",
        "nav.agents": "Agents",
        "nav.tasks": "Tasks",
        "nav.social": "Social",
        "nav.outreach": "Outreach",
        "nav.ads": "Ads",
        "nav.finance": "Finance",
        "nav.memory": "Memory",
        "nav.settings": "Settings",
        "nav.quota": "Quota",
        "nav.mcp": "MCP Tools",
        "nav.plugins": "Plugins",
        "nav.audit": "Audit Chain",
        "nav.scheduler": "Scheduler",
        "nav.sandbox": "Sandbox",
        "nav.marketplace": "Marketplace",
        "nav.group.operations": "Operations",
        "nav.group.system": "System",
        "brand.subtitle": "AI Agent Platform",
        "nav.lang": "中文",
        "nav.search": "Search",
      };
      return map[key] ?? key;
    },
  }),
}));

describe("Sidebar", () => {
  it("renders all nav items", () => {
    render(<Sidebar />);
    expect(screen.getByText("Dashboard")).toBeInTheDocument();
    expect(screen.getByText("Agents")).toBeInTheDocument();
    expect(screen.getByText("Finance")).toBeInTheDocument();
    expect(screen.getByText("Settings")).toBeInTheDocument();
    expect(screen.getByText("Quota")).toBeInTheDocument();
    expect(screen.getByText("MCP Tools")).toBeInTheDocument();
    expect(screen.getByText("Plugins")).toBeInTheDocument();
    expect(screen.getByText("Audit Chain")).toBeInTheDocument();
    expect(screen.getByText("Scheduler")).toBeInTheDocument();
    expect(screen.getByText("Sandbox")).toBeInTheDocument();
    expect(screen.getByText("Marketplace")).toBeInTheDocument();
  });

  it("renders section group headers", () => {
    render(<Sidebar />);
    expect(screen.getByText("Operations")).toBeInTheDocument();
    expect(screen.getByText("System")).toBeInTheDocument();
  });

  it("highlights the active route", () => {
    render(<Sidebar />);
    const dashboardLink = screen.getByText("Dashboard").closest("a");
    expect(dashboardLink).toHaveClass("bg-indigo-600");
  });

  it("shows the app title", () => {
    render(<Sidebar />);
    expect(screen.getByText("Polsia")).toBeInTheDocument();
  });

  it("renders search button", () => {
    render(<Sidebar />);
    expect(screen.getByText("Search")).toBeInTheDocument();
  });
});
