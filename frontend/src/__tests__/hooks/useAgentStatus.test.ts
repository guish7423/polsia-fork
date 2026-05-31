import "@testing-library/jest-dom";
import { act, renderHook } from "@testing-library/react";
import { useAgentStatus } from "@/hooks/useAgentStatus";
import { api } from "@/lib/api";

jest.mock("@/lib/api", () => ({
  api: { get: jest.fn() },
}));

const mockApiGet = api.get as jest.Mock;

const mockStatuses = [
  { agent_type: "finance", last_run_status: "completed", last_run_at: null, tasks_today: 1, tasks_total: 5 },
];

describe("useAgentStatus", () => {
  beforeEach(() => {
    jest.useFakeTimers();
    mockApiGet.mockReset();
  });

  afterEach(() => {
    jest.useRealTimers();
  });

  it("starts in loading state", () => {
    mockApiGet.mockResolvedValue([]);
    const { result } = renderHook(() => useAgentStatus());
    expect(result.current.loading).toBe(true);
    expect(result.current.statuses).toEqual([]);
  });

  it("fetches statuses on mount", async () => {
    mockApiGet.mockResolvedValue(mockStatuses);
    const { result } = renderHook(() => useAgentStatus());

    // Flush pending promises
    await act(async () => { jest.advanceTimersByTime(0); });

    expect(result.current.loading).toBe(false);
    expect(result.current.statuses).toEqual(mockStatuses);
    expect(result.current.error).toBeNull();
  });

  it("polls at the given interval", async () => {
    mockApiGet.mockResolvedValue(mockStatuses);
    renderHook(() => useAgentStatus(5000));

    // Flush initial fetch
    await act(async () => { jest.advanceTimersByTime(0); });
    expect(mockApiGet).toHaveBeenCalledTimes(1);

    // Advance by one interval
    await act(async () => { jest.advanceTimersByTime(5000); });
    expect(mockApiGet).toHaveBeenCalledTimes(2);

    // Advance by another interval
    await act(async () => { jest.advanceTimersByTime(5000); });
    expect(mockApiGet).toHaveBeenCalledTimes(3);
  });

  it("sets error on fetch failure", async () => {
    mockApiGet.mockRejectedValue(new Error("Network error"));
    const { result } = renderHook(() => useAgentStatus());

    await act(async () => { jest.advanceTimersByTime(0); });

    expect(result.current.loading).toBe(false);
    expect(result.current.error).toContain("Network error");
  });

  it("stops polling on unmount", async () => {
    mockApiGet.mockResolvedValue(mockStatuses);
    const { unmount } = renderHook(() => useAgentStatus(1000));

    // Flush initial fetch
    await act(async () => { jest.advanceTimersByTime(0); });
    expect(mockApiGet).toHaveBeenCalledTimes(1);

    unmount();

    // Advance time — no new calls should happen
    await act(async () => { jest.advanceTimersByTime(5000); });
    expect(mockApiGet).toHaveBeenCalledTimes(1);
  });
});
