"use client";

import { FormEvent, useEffect, useMemo, useRef, useState } from "react";

type RunPhase = "idle" | "running" | "completed" | "failed";

type Strategy = "quick" | "standard" | "deep" | "academic";

interface RunRequest {
  thread_id: string;
  user_request: string;
  strategy: Strategy;
  max_concurrency: number;
  max_tasks: number;
}

interface StreamEvent {
  workflow_id: string;
  type: string;
  agent_id: string;
  message: string;
  payload: Record<string, unknown>;
  timestamp: number;
  seq: number;
  stream_id: string;
}

interface AgentTimelineItem {
  key: string;
  seq: number;
  timestamp: number;
  flow: string;
  action: string;
  taskId: string;
  status: string;
  detail: string;
}

interface StateResponse {
  thread_id: string;
  state: Record<string, unknown>;
}

interface StateDbResponse {
  thread_id: string;
  state: Record<string, unknown>;
}

interface RunResponse {
  thread_id: string;
  state: Record<string, unknown>;
}

function formatTimestamp(epochSec: number): string {
  if (!epochSec) return "-";
  return new Date(epochSec * 1000).toLocaleTimeString();
}

function prettyJson(value: unknown): string {
  return JSON.stringify(value ?? {}, null, 2);
}

function newThreadId(): string {
  return `debug-${Date.now()}`;
}

function payloadString(payload: Record<string, unknown>, key: string, fallback = "-"): string {
  const value = payload[key];
  return typeof value === "string" && value ? value : fallback;
}

export default function HomePage() {
  const [threadId, setThreadId] = useState<string>("");
  const [userRequest, setUserRequest] = useState<string>("Generate a small benchmark dataset for customer support FAQ intent classification.");
  const [strategy, setStrategy] = useState<Strategy>("deep");
  const [maxConcurrency, setMaxConcurrency] = useState<number>(3);
  const [maxTasks, setMaxTasks] = useState<number>(6);

  const [phase, setPhase] = useState<RunPhase>("idle");
  const [isPolling, setIsPolling] = useState<boolean>(false);
  const [events, setEvents] = useState<StreamEvent[]>([]);
  const [stateSnapshot, setStateSnapshot] = useState<Record<string, unknown> | null>(null);
  const [stateDbSnapshot, setStateDbSnapshot] = useState<Record<string, unknown> | null>(null);
  const [runResponse, setRunResponse] = useState<RunResponse | null>(null);
  const [errorText, setErrorText] = useState<string>("");

  const sinceSeqRef = useRef<number>(0);

  useEffect(() => {
    if (!threadId) {
      setThreadId(newThreadId());
    }
  }, [threadId]);

  const totalEvents = events.length;
  const lastSeq = useMemo(() => {
    if (!events.length) return 0;
    return Math.max(...events.map((event) => Number(event.seq) || 0));
  }, [events]);
  const agentTimeline = useMemo<AgentTimelineItem[]>(() => {
    const trackedTypes = new Set([
      "AGENT_CALL_STARTED",
      "AGENT_CALL_COMPLETED",
      "AGENT_CALL_FAILED",
      "AGENT_HANDOFF",
      "AGENT_BLOCKED",
      "TASK_BATCH_SCHEDULED"
    ]);

    return events
      .filter((item) => trackedTypes.has(item.type))
      .map((item) => {
        const payload = item.payload || {};
        if (item.type.startsWith("AGENT_CALL_")) {
          const fromAgent = payloadString(payload, "from_agent", item.agent_id || "-");
          const toAgent = payloadString(payload, "to_agent", "-");
          const callName = payloadString(payload, "call_name", item.type);
          const taskId = payloadString(payload, "task_id", "-");
          const status =
            payloadString(payload, "status", "").toLowerCase() ||
            (item.type.endsWith("FAILED")
              ? "failed"
              : item.type.endsWith("COMPLETED")
                ? "completed"
                : "running");
          const detail = payloadString(payload, "error", item.message || "");
          return {
            key: `${item.seq}-${item.stream_id}-agent-call`,
            seq: Number(item.seq) || 0,
            timestamp: Number(item.timestamp) || 0,
            flow: `${fromAgent} -> ${toAgent}`,
            action: callName,
            taskId,
            status,
            detail
          };
        }

        if (item.type === "TASK_BATCH_SCHEDULED") {
          const activeTaskIds = Array.isArray(payload.active_task_ids)
            ? payload.active_task_ids.map((taskId) => String(taskId)).join(", ")
            : "";
          return {
            key: `${item.seq}-${item.stream_id}-batch`,
            seq: Number(item.seq) || 0,
            timestamp: Number(item.timestamp) || 0,
            flow: "orchestrator.schedule -> task_agents",
            action: "dispatch_batch",
            taskId: activeTaskIds || "-",
            status: "scheduled",
            detail: activeTaskIds ? `active_tasks: ${activeTaskIds}` : item.message
          };
        }

        const fromTaskId = payloadString(payload, "from_task_id", "-");
        const toTaskId = payloadString(payload, "to_task_id", "-");
        const isBlocked = item.type === "AGENT_BLOCKED";
        return {
          key: `${item.seq}-${item.stream_id}-handoff`,
          seq: Number(item.seq) || 0,
          timestamp: Number(item.timestamp) || 0,
          flow: `task:${fromTaskId} -> task:${toTaskId}`,
          action: isBlocked ? "blocked" : "handoff",
          taskId: toTaskId,
          status: isBlocked ? "blocked" : "handoff",
          detail: payloadString(payload, "reason", item.message)
        };
      })
      .sort((a, b) => a.seq - b.seq);
  }, [events]);

  useEffect(() => {
    sinceSeqRef.current = lastSeq;
  }, [lastSeq]);

  useEffect(() => {
    if (!isPolling || !threadId) {
      return;
    }

    const streamUrl = `/api/threads/${encodeURIComponent(threadId)}/events/stream?since_seq=${sinceSeqRef.current}`;
    const source = new EventSource(streamUrl);

    source.onmessage = (message) => {
      try {
        const item = JSON.parse(message.data) as StreamEvent;
        const seq = Number(item.seq) || 0;
        sinceSeqRef.current = Math.max(sinceSeqRef.current, seq);

        setEvents((prev) => {
          const map = new Map<string, StreamEvent>();
          for (const row of prev) map.set(`${row.seq}-${row.stream_id}`, row);
          map.set(`${item.seq}-${item.stream_id}`, item);
          const merged = Array.from(map.values()).sort((a, b) => (a.seq || 0) - (b.seq || 0));
          if (merged.length > 1200) {
            return merged.slice(-1200);
          }
          return merged;
        });

        if (item.type === "WORKFLOW_COMPLETED") setPhase("completed");
        if (item.type === "WORKFLOW_FAILED") setPhase("failed");
      } catch (error) {
        setErrorText(`Invalid stream payload: ${error instanceof Error ? error.message : String(error)}`);
      }
    };

    source.onerror = () => {
      if (isPolling) setErrorText("Event stream disconnected.");
      source.close();
    };

    return () => {
      source.close();
    };
  }, [isPolling, threadId]);

  useEffect(() => {
    if (!isPolling || !threadId) {
      return;
    }

    let canceled = false;
    let pending = false;

    const tick = async () => {
      if (pending || canceled || !isPolling) return;
      pending = true;
      try {
        const stateRes = await fetch(`/api/threads/${encodeURIComponent(threadId)}/state`, {
          cache: "no-store"
        });
        if (stateRes.ok) {
          const payload: StateResponse = await stateRes.json();
          setStateSnapshot(payload.state || null);
        }

        const stateDbRes = await fetch(`/api/threads/${encodeURIComponent(threadId)}/state-db`, {
          cache: "no-store"
        });
        if (stateDbRes.ok) {
          const payload: StateDbResponse = await stateDbRes.json();
          setStateDbSnapshot(payload.state || null);
        }
      } catch (error) {
        if (!canceled) {
          setErrorText(`Polling failed: ${error instanceof Error ? error.message : String(error)}`);
        }
      } finally {
        pending = false;
      }
    };

    void tick();
    const timer = window.setInterval(() => {
      void tick();
    }, 1200);

    return () => {
      canceled = true;
      window.clearInterval(timer);
    };
  }, [isPolling, threadId]);

  const startPolling = () => {
    setIsPolling(true);
  };

  const stopPolling = () => {
    setIsPolling(false);
  };

  const onSubmit = async (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    setErrorText("");

    const runPayload: RunRequest = {
      thread_id: threadId.trim(),
      user_request: userRequest.trim(),
      strategy,
      max_concurrency: maxConcurrency,
      max_tasks: maxTasks
    };

    if (!runPayload.thread_id || !runPayload.user_request) {
      setErrorText("thread_id and user_request are required");
      return;
    }

    setEvents([]);
    setRunResponse(null);
    setStateSnapshot(null);
    setStateDbSnapshot(null);
    sinceSeqRef.current = 0;
    setPhase("running");
    startPolling();

    try {
      const response = await fetch("/api/runs", {
        method: "POST",
        headers: {
          "content-type": "application/json"
        },
        body: JSON.stringify(runPayload)
      });

      if (!response.ok) {
        const text = await response.text();
        setPhase("failed");
        setErrorText(`Run failed: ${response.status} ${text}`);
        return;
      }

      const payload: RunResponse = await response.json();
      setRunResponse(payload);
      setStateSnapshot(payload.state || null);
      setPhase("completed");
    } catch (error) {
      setPhase("failed");
      setErrorText(`Run request failed: ${error instanceof Error ? error.message : String(error)}`);
    } finally {
      window.setTimeout(() => {
        stopPolling();
      }, 4000);
    }
  };

  const resetThread = () => {
    setThreadId(newThreadId());
    setEvents([]);
    setStateSnapshot(null);
    setStateDbSnapshot(null);
    setRunResponse(null);
    setErrorText("");
    setPhase("idle");
    sinceSeqRef.current = 0;
    stopPolling();
  };

  return (
    <main>
      <section className="header">
        <h1>Shannon Debug Console</h1>
        <p>Web-mode dashboard for task execution and event stream debugging.</p>
      </section>

      <div className="layout">
        <section className="panel">
          <form onSubmit={onSubmit}>
            <div className="form-row">
              <label htmlFor="thread-id">Thread ID</label>
              <input
                id="thread-id"
                value={threadId}
                onChange={(e) => setThreadId(e.target.value)}
                placeholder="debug-xxxx"
              />
            </div>

            <div className="form-row">
              <label htmlFor="strategy">Strategy</label>
              <select id="strategy" value={strategy} onChange={(e) => setStrategy(e.target.value as Strategy)}>
                <option value="quick">quick</option>
                <option value="standard">standard</option>
                <option value="deep">deep</option>
                <option value="academic">academic</option>
              </select>
            </div>

            <div className="form-row">
              <label htmlFor="max-concurrency">Max Concurrency</label>
              <input
                id="max-concurrency"
                type="number"
                min={1}
                max={16}
                value={maxConcurrency}
                onChange={(e) => setMaxConcurrency(Number(e.target.value || 1))}
              />
            </div>

            <div className="form-row">
              <label htmlFor="max-tasks">Max Tasks</label>
              <input
                id="max-tasks"
                type="number"
                min={1}
                max={30}
                value={maxTasks}
                onChange={(e) => setMaxTasks(Number(e.target.value || 1))}
              />
            </div>

            <div className="form-row">
              <label htmlFor="user-request">User Request</label>
              <textarea
                id="user-request"
                value={userRequest}
                onChange={(e) => setUserRequest(e.target.value)}
                placeholder="Describe your dataset/research intent"
              />
            </div>

            <div className="form-row">
              <button type="submit" disabled={phase === "running"}>
                {phase === "running" ? "Running..." : "Run Workflow"}
              </button>
            </div>

            <div className="form-row">
              <button type="button" onClick={resetThread}>
                New Thread
              </button>
            </div>
          </form>

          {errorText ? <div className="error">{errorText}</div> : null}
        </section>

        <section className="panel">
          <div>
            <h2>Run Overview</h2>
            <p>
              <span className={`badge ${phase}`}>{phase.toUpperCase()}</span>
            </p>
          </div>

          <div className="meta-grid">
            <article className="meta-item">
              <h3>Thread ID</h3>
              <p>{threadId || "-"}</p>
            </article>
            <article className="meta-item">
              <h3>Total Events</h3>
              <p>{totalEvents}</p>
            </article>
            <article className="meta-item">
              <h3>Last Seq</h3>
              <p>{lastSeq}</p>
            </article>
            <article className="meta-item">
              <h3>Run Response</h3>
              <p>{runResponse ? "received" : "pending"}</p>
            </article>
          </div>

          <div className="columns" style={{ marginTop: 16 }}>
            <article>
              <h3>Event Stream</h3>
              <ul className="log-list">
                {events.length === 0 ? (
                  <li>No events yet.</li>
                ) : (
                  events.map((item) => (
                    <li key={`${item.seq}-${item.stream_id}`}>
                      [{item.seq}] {formatTimestamp(item.timestamp)} {item.type}
                      {item.message ? ` - ${item.message}` : ""}
                    </li>
                  ))
                )}
              </ul>
            </article>

            <article>
              <h3>Agent Call Timeline</h3>
              <ul className="timeline-list">
                {agentTimeline.length === 0 ? (
                  <li>No agent call events yet.</li>
                ) : (
                  agentTimeline.map((item) => (
                    <li key={item.key}>
                      <div className="timeline-head">
                        [{item.seq}] {formatTimestamp(item.timestamp)} {item.flow}
                      </div>
                      <div className="timeline-detail">
                        action={item.action} task={item.taskId} status={item.status}
                      </div>
                      {item.detail ? <div className="timeline-detail">{item.detail}</div> : null}
                    </li>
                  ))
                )}
              </ul>
            </article>
          </div>

          <article style={{ marginTop: 16 }}>
            <h3>Event Payload (latest)</h3>
            <pre>{prettyJson(events.at(-1)?.payload || {})}</pre>
          </article>

          <div className="columns" style={{ marginTop: 16 }}>
            <article>
              <h3>Live State (/state)</h3>
              <pre>{prettyJson(stateSnapshot)}</pre>
            </article>
            <article>
              <h3>Persisted State (/state_db)</h3>
              <pre>{prettyJson(stateDbSnapshot)}</pre>
            </article>
          </div>
        </section>
      </div>
    </main>
  );
}
