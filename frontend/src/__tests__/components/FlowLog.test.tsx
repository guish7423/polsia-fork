import "@testing-library/jest-dom";
import { render, screen, act, fireEvent } from "@testing-library/react";
import { FlowLog } from "@/components/agents/FlowLog";

// ─── Mock EventSource ──────────────────────────────────────────────────────
let mockOnOpen: (() => void) | null = null;
let mockOnError: ((err: Event) => void) | null = null;
const stepListeners = new Set<(data: string) => void>();
let closeCount = 0;
let esInstance: any = null;

class MockEventSource {
  static CONNECTING = 0;
  static OPEN = 1;
  static CLOSED = 2;
  readyState = MockEventSource.CONNECTING;
  url: string;
  onopen: (() => void) | null = null;
  onerror: ((err: Event) => void) | null = null;

  constructor(url: string) {
    this.url = url;
    esInstance = this;
    mockOnOpen = () => {
      this.readyState = MockEventSource.OPEN;
      this.onopen?.();
    };
    mockOnError = (err: Event) => {
      this.readyState = MockEventSource.CLOSED;
      this.onerror?.(err);
    };
  }

  addEventListener(type: string, cb: (e: MessageEvent) => void) {
    if (type === "step") {
      stepListeners.add((data: string) => cb(new MessageEvent("step", { data })));
    }
  }

  close() {
    closeCount++;
    this.readyState = MockEventSource.CLOSED;
  }
}

(globalThis as any).EventSource = MockEventSource;

function emitStep(data: unknown) {
  const json = JSON.stringify(data);
  stepListeners.forEach((cb) => cb(json));
}

// ─── Tests ─────────────────────────────────────────────────────────────────

describe("FlowLog", () => {
  beforeEach(() => {
    stepListeners.clear();
    mockOnOpen = null;
    mockOnError = null;
    closeCount = 0;
    esInstance = null;
  });

  it("shows connecting status on mount", () => {
    render(<FlowLog agentType="orchestrator" open={true} onClose={() => {}} />);
    expect(screen.getByText("Connecting...")).toBeInTheDocument();
  });

  it("shows Live after EventSource opens", () => {
    render(<FlowLog agentType="orchestrator" open={true} onClose={() => {}} />);
    act(() => mockOnOpen?.());
    expect(screen.getByText("Live")).toBeInTheDocument();
  });

  it("renders received step messages", () => {
    render(<FlowLog agentType="orchestrator" open={true} onClose={() => {}} />);
    act(() => {
      mockOnOpen?.();
      emitStep({ step: "thinking", content: "Analyzing...", ts: "10:00:01" });
      emitStep({ step: "result", content: "Done", ts: "10:00:02" });
    });
    expect(screen.getByText("Analyzing...")).toBeInTheDocument();
    expect(screen.getByText("Done")).toBeInTheDocument();
  });

  it("closes EventSource on unmount", () => {
    const { unmount } = render(<FlowLog agentType="orchestrator" open={true} onClose={() => {}} />);
    expect(closeCount).toBe(0);
    unmount();
    expect(closeCount).toBe(1);
  });

  it("caps at 100 entries", () => {
    render(<FlowLog agentType="orchestrator" open={true} onClose={() => {}} />);
    act(() => {
      mockOnOpen?.();
      for (let i = 0; i < 102; i++) {
        emitStep({ step: "thinking", content: `entry ${i}`, ts: "10:00:00" });
      }
    });
    const entries = screen.getAllByText(/entry \d+/);
    expect(entries[0]).toHaveTextContent("entry 2");
    expect(entries.length).toBe(100);
  });

  it("does not connect EventSource when closed", () => {
    render(<FlowLog agentType="orchestrator" open={false} onClose={() => {}} />);
    expect(esInstance).toBeNull();
  });
});
