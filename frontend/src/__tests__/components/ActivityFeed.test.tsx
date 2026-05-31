import "@testing-library/jest-dom";
import { render, screen } from "@testing-library/react";
import { ActivityFeed } from "@/components/dashboard/ActivityFeed";

// Mock the hook instead of WebSocket — cleaner and more reliable
const mockUseActivityFeed = jest.fn();
jest.mock("@/hooks/useActivityFeed", () => ({
  useActivityFeed: () => mockUseActivityFeed(),
}));

describe("ActivityFeed", () => {
  beforeEach(() => {
    mockUseActivityFeed.mockReset();
  });

  it("renders empty state when no events", () => {
    mockUseActivityFeed.mockReturnValue({ events: [], connected: false });
    render(<ActivityFeed />);
    expect(screen.getByText(/No activity yet/i)).toBeInTheDocument();
  });

  it("shows 'Live' status when connected", () => {
    mockUseActivityFeed.mockReturnValue({ events: [], connected: true });
    render(<ActivityFeed />);
    expect(screen.getByText("Live")).toBeInTheDocument();
  });

  it("renders events received via WebSocket", () => {
    const event = {
      id: 1,
      agent_type: "social_media",
      action: "post_tweet",
      summary: "Posted a tweet about our launch",
      level: "success",
      created_at: new Date().toISOString(),
    };
    mockUseActivityFeed.mockReturnValue({ events: [event], connected: true });
    render(<ActivityFeed />);

    expect(screen.getByText("social_media")).toBeInTheDocument();
    expect(screen.getByText("Posted a tweet about our launch")).toBeInTheDocument();
  });

  it("shows reconnecting state when disconnected", () => {
    mockUseActivityFeed.mockReturnValue({ events: [], connected: false });
    render(<ActivityFeed />);
    expect(screen.queryByText("Live")).not.toBeInTheDocument();
  });
});
