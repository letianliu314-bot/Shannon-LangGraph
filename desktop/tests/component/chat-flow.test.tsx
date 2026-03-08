import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { vi } from "vitest";
import HomePage from "@/app/page";

class EventSourceMock {
  static instances: EventSourceMock[] = [];
  onmessage: ((event: MessageEvent) => void) | null = null;
  onopen: (() => void) | null = null;
  onerror: (() => void) | null = null;
  readyState = 1;

  constructor(_url: string) {
    EventSourceMock.instances.push(this);
    setTimeout(() => this.onopen?.(), 0);
  }

  close() {
    this.readyState = 2;
  }

  emit(data: unknown) {
    this.onmessage?.({ data: JSON.stringify(data) } as MessageEvent);
  }
}

function mockFetch() {
  global.fetch = vi.fn(async (input: string | URL, init?: RequestInit) => {
    const url = String(input);

    if (url.includes("/api/runs") && init?.method === "POST") {
      return new Response(JSON.stringify({ thread_id: "thread-1", status: "accepted" }), { status: 202 });
    }

    if (url.includes("/api/threads/") && url.includes("/events?")) {
      return new Response(JSON.stringify({ events: [] }), { status: 200 });
    }

    if (url.includes("/api/threads/") && url.endsWith("/session")) {
      return new Response(JSON.stringify({ thread_id: "thread-1", session: { messages: [] } }), { status: 200 });
    }

    if (url.includes("/api/threads/") && url.endsWith("/state-db")) {
      return new Response(JSON.stringify({ thread_id: "thread-1", state: { db: true } }), { status: 200 });
    }

    if (url.includes("/api/threads/") && url.endsWith("/state")) {
      return new Response(
        JSON.stringify({
          thread_id: "thread-1",
          state: { final_output: { summary: "这是最终回答" } }
        }),
        { status: 200 }
      );
    }

    return new Response(JSON.stringify({}), { status: 200 });
  }) as typeof fetch;
}

describe("HomePage component flow", () => {
  beforeEach(() => {
    EventSourceMock.instances = [];
    global.EventSource = EventSourceMock as unknown as typeof EventSource;
    mockFetch();
    localStorage.clear();
  });

  it("enters running state then renders assistant reply and graph node", async () => {
    render(<HomePage />);

    const input = await screen.findByLabelText("composer-input");
    fireEvent.change(input, { target: { value: "你好" } });
    fireEvent.click(screen.getByText("发送"));

    expect(await screen.findByText("run: running")).toBeInTheDocument();

    await waitFor(() => {
      expect(EventSourceMock.instances.length).toBeGreaterThan(0);
    });

    const source = EventSourceMock.instances[0];
    source.emit({
      type: "AGENT_CALL_STARTED",
      seq: 1,
      stream_id: "a",
      timestamp: 1700000000,
      payload: {
        from_agent: "orchestrator",
        to_agent: "research_agent",
        task_id: "task-1"
      }
    });
    source.emit({
      type: "WORKFLOW_COMPLETED",
      seq: 2,
      stream_id: "b",
      timestamp: 1700000001,
      payload: {}
    });

    expect(await screen.findByText("这是最终回答")).toBeInTheDocument();
    expect(await screen.findByText("task-1")).toBeInTheDocument();
  });
});
