import "@testing-library/jest-dom";
import { render, screen } from "@testing-library/react";
import { QuotaDonut } from "@/components/dashboard/QuotaDonut";

describe("QuotaDonut", () => {
  it("renders label, current/limit, and usage percentage", () => {
    render(<QuotaDonut labelKey="quota.agents" current={5} limit={10} usagePct={50} color="#818cf8" />);
    expect(screen.getByText("50%")).toBeInTheDocument();
    expect(screen.getByText("5 / 10")).toBeInTheDocument();
  });

  it("renders 0% state correctly", () => {
    render(<QuotaDonut labelKey="quota.tasks" current={0} limit={100} usagePct={0} color="#34d399" />);
    expect(screen.getByText("0%")).toBeInTheDocument();
    expect(screen.getByText("0 / 100")).toBeInTheDocument();
  });

  it("renders 100% state correctly", () => {
    render(<QuotaDonut labelKey="quota.tokens" current={1000} limit={1000} usagePct={100} color="#fbbf24" />);
    expect(screen.getByText("100%")).toBeInTheDocument();
    expect(screen.getByText("1,000 / 1,000")).toBeInTheDocument();
  });

  it("renders SVG circle elements", () => {
    const { container } = render(
      <QuotaDonut labelKey="quota.cost" current={50.5} limit={200} usagePct={25.25} color="#f472b6" />
    );
    const circles = container.querySelectorAll("svg circle");
    expect(circles.length).toBe(2); // background ring + progress ring
  });

  it("shows allowed badge when allowed=true", () => {
    render(
      <QuotaDonut labelKey="quota.agents" current={3} limit={10} usagePct={30} color="#818cf8" allowed />
    );
    expect(screen.getByText("Allowed")).toBeInTheDocument();
  });
});
