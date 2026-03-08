import { describe, expect, it } from "vitest";
import { initialEventUiState, reduceWithEvent } from "@/lib/events/reducer";
import { StreamEvent } from "@/lib/types";

function makeEvent(partial: Partial<StreamEvent>): StreamEvent {
  return {
    type: "WORKFLOW_STARTED",
    payload: {},
    timestamp: 1,
    seq: 1,
    stream_id: "stream-1",
    ...partial
  };
}

describe("event reducer", () => {
  it("evolves run phase for key workflow events", () => {
    const started = reduceWithEvent(initialEventUiState, makeEvent({ type: "WORKFLOW_STARTED", seq: 1 }));
    const completed = reduceWithEvent(started, makeEvent({ type: "WORKFLOW_COMPLETED", seq: 2, stream_id: "stream-2" }));

    expect(started.phase).toBe("running");
    expect(completed.phase).toBe("completed");
    expect(completed.lastSeq).toBe(2);
  });

  it("deduplicates events by seq + stream_id", () => {
    const event = makeEvent({ type: "AGENT_CALL_STARTED", seq: 3, stream_id: "same" });
    const once = reduceWithEvent(initialEventUiState, event);
    const twice = reduceWithEvent(once, event);
    expect(twice.events).toHaveLength(1);
  });
});
