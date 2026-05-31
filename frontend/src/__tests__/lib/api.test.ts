/**
 * @jest-environment node
 */
import { api } from "@/lib/api";

// Mock global fetch
const mockFetch = jest.fn();
global.fetch = mockFetch;

describe("api client", () => {
  beforeEach(() => {
    mockFetch.mockReset();
  });

  it("api.get makes GET request with correct path", async () => {
    mockFetch.mockResolvedValue({
      ok: true,
      json: async () => ({ mrr_cents: 847300 }),
    });

    const result = await api.get("/finance/summary");
    expect(mockFetch).toHaveBeenCalledWith(
      expect.stringContaining("/api/v1/finance/summary"),
      expect.objectContaining({
        headers: expect.objectContaining({
          "Content-Type": "application/json",
          "X-API-Key": expect.any(String),
        }),
      }),
    );
    expect(result).toEqual({ mrr_cents: 847300 });
  });

  it("api.post sends JSON body", async () => {
    mockFetch.mockResolvedValue({
      ok: true,
      json: async () => ({ message: "Agent triggered" }),
    });

    const result = await api.post("/agents/orchestrator/trigger", { reason: "test" });
    expect(mockFetch).toHaveBeenCalledWith(
      expect.stringContaining("/api/v1/agents/orchestrator/trigger"),
      expect.objectContaining({
        method: "POST",
        body: JSON.stringify({ reason: "test" }),
      }),
    );
    expect(result).toEqual({ message: "Agent triggered" });
  });

  it("api.put sends JSON body", async () => {
    mockFetch.mockResolvedValue({
      ok: true,
      json: async () => ({ name: "My Company" }),
    });

    const result = await api.put("/config", { name: "My Company" });
    expect(mockFetch).toHaveBeenCalledWith(
      expect.stringContaining("/api/v1/config"),
      expect.objectContaining({
        method: "PUT",
        body: JSON.stringify({ name: "My Company" }),
      }),
    );
    expect(result).toEqual({ name: "My Company" });
  });

  it("throws on non-ok response with detail text", async () => {
    mockFetch.mockResolvedValue({
      ok: false,
      status: 403,
      statusText: "Forbidden",
      text: async () => "Invalid API key",
    });

    await expect(api.get("/config")).rejects.toThrow("API 403: Invalid API key");
  });

  it("throws with statusText when response text fails", async () => {
    mockFetch.mockResolvedValue({
      ok: false,
      status: 500,
      statusText: "Internal Server Error",
      text: async () => { throw new Error("stream error"); },
    });

    await expect(api.get("/dashboard/summary")).rejects.toThrow("API 500: Internal Server Error");
  });

  it("includes X-API-Key header in all requests", async () => {
    mockFetch.mockResolvedValue({
      ok: true,
      json: async () => ({}),
    });

    await api.get("/health");
    expect(mockFetch).toHaveBeenCalledWith(
      expect.stringContaining("/api/v1/health"),
      expect.objectContaining({
        headers: expect.objectContaining({ "X-API-Key": expect.any(String) }),
      }),
    );
  });
});
