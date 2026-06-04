import "@testing-library/jest-dom";
import { render, screen, fireEvent, waitFor } from "@testing-library/react";
import { NotificationBell } from "@/components/layout/NotificationBell";

const mockPush = jest.fn();
jest.mock("next/navigation", () => ({
  useRouter: () => ({ push: mockPush }),
}));

const mockFetchUnreadCount = jest.fn();
const mockFetchNotifications = jest.fn();
const mockMarkRead = jest.fn();
const mockMarkAllRead = jest.fn();

jest.mock("@/lib/api", () => ({
  ...jest.requireActual("@/lib/api"),
  fetchUnreadCount: (...args: unknown[]) => mockFetchUnreadCount(...args),
  fetchNotifications: (...args: unknown[]) => mockFetchNotifications(...args),
  markNotificationRead: (...args: unknown[]) => mockMarkRead(...args),
  markAllNotificationsRead: (...args: unknown[]) => mockMarkAllRead(...args),
}));

jest.mock("@/lib/i18n", () => ({
  useI18n: () => ({
    locale: "en",
    setLocale: jest.fn(),
    t: (key: string) => {
      const map: Record<string, string> = {
        "notification.title": "Notifications",
        "notification.empty": "✅ No new notifications",
        "notification.mark_all_read": "Mark all read",
        "notification.just_now": "Just now",
        "notification.minutes_ago": "{n}m ago",
        "notification.hours_ago": "{n}h ago",
        "notification.days_ago": "{n}d ago",
      };
      return map[key] ?? key;
    },
  }),
}));

const mockNotifications = [
  {
    id: 1,
    tenant_id: 1,
    notification_type: "alert" as const,
    title: "High CPU usage",
    body: "CPU has been above 90% for 10 minutes",
    read: false,
    read_at: null,
    link: "/alerts/1",
    created_at: new Date().toISOString(),
  },
  {
    id: 2,
    tenant_id: 1,
    notification_type: "billing" as const,
    title: "Invoice generated",
    body: "Monthly invoice for June is ready",
    read: false,
    read_at: null,
    link: "/finance",
    created_at: new Date(Date.now() - 3_600_000).toISOString(),
  },
  {
    id: 3,
    tenant_id: 1,
    notification_type: "system" as const,
    title: "Weekly report ready",
    body: null,
    read: true,
    read_at: new Date().toISOString(),
    link: null,
    created_at: new Date(Date.now() - 86_400_000).toISOString(),
  },
];

beforeEach(() => {
  jest.clearAllMocks();
  mockFetchUnreadCount.mockResolvedValue({ count: 2 });
  mockFetchNotifications.mockResolvedValue({
    total: 3,
    limit: 10,
    offset: 0,
    items: mockNotifications,
  });
  mockMarkRead.mockResolvedValue(undefined);
  mockMarkAllRead.mockResolvedValue(undefined);
});

describe("NotificationBell", () => {
  it("renders bell icon with unread badge count", async () => {
    render(<NotificationBell />);
    await waitFor(() => {
      expect(mockFetchUnreadCount).toHaveBeenCalled();
    });

    expect(screen.getByLabelText("Notifications")).toBeInTheDocument();
    expect(screen.getByText("2")).toBeInTheDocument();
  });

  it("opens dropdown on click and shows notifications list", async () => {
    render(<NotificationBell />);

    await waitFor(() => {
      expect(mockFetchUnreadCount).toHaveBeenCalled();
    });

    // Click the bell
    const bell = screen.getByLabelText("Notifications");
    fireEvent.click(bell);

    await waitFor(() => {
      expect(mockFetchNotifications).toHaveBeenCalledWith(10, 0);
    });

    // Should show both unread notification titles
    expect(screen.getByText("High CPU usage")).toBeInTheDocument();
    expect(screen.getByText("Invoice generated")).toBeInTheDocument();
    // Read notification should also appear
    expect(screen.getByText("Weekly report ready")).toBeInTheDocument();
  });

  it("shows empty state when no notifications", async () => {
    mockFetchNotifications.mockResolvedValue({
      total: 0,
      limit: 10,
      offset: 0,
      items: [],
    });

    render(<NotificationBell />);

    await waitFor(() => {
      expect(mockFetchUnreadCount).toHaveBeenCalled();
    });

    fireEvent.click(screen.getByLabelText("Notifications"));

    await waitFor(() => {
      expect(screen.getByText("✅ No new notifications")).toBeInTheDocument();
    });
  });

  it("marks notification read and navigates on click", async () => {
    render(<NotificationBell />);

    await waitFor(() => {
      expect(mockFetchUnreadCount).toHaveBeenCalled();
    });

    fireEvent.click(screen.getByLabelText("Notifications"));

    await waitFor(() => {
      expect(screen.getByText("High CPU usage")).toBeInTheDocument();
    });

    // Click notification item
    fireEvent.click(screen.getByText("High CPU usage"));

    await waitFor(() => {
      expect(mockMarkRead).toHaveBeenCalledWith(1);
      expect(mockPush).toHaveBeenCalledWith("/alerts/1");
    });
  });

  it("marks all notifications as read via button", async () => {
    render(<NotificationBell />);

    await waitFor(() => {
      expect(mockFetchUnreadCount).toHaveBeenCalled();
    });

    fireEvent.click(screen.getByLabelText("Notifications"));

    await waitFor(() => {
      expect(screen.getByText("Mark all read")).toBeInTheDocument();
    });

    fireEvent.click(screen.getByText("Mark all read"));

    await waitFor(() => {
      expect(mockMarkAllRead).toHaveBeenCalled();
    });

    // Badge should be gone
    expect(screen.queryByText("2")).not.toBeInTheDocument();
  });
});
