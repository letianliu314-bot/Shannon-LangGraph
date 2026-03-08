"use client";

import { useCallback, useEffect, useMemo, useState } from "react";
import { Node } from "@xyflow/react";
import { Composer } from "@/components/chat/Composer";
import { MessageList } from "@/components/chat/MessageList";
import { RunStatus } from "@/components/chat/RunStatus";
import { CallGraph } from "@/components/graph/CallGraph";
import { GraphLegend } from "@/components/graph/GraphLegend";
import { NodeDetails } from "@/components/graph/NodeDetails";
import { useChatThread } from "@/hooks/useChatThread";
import { useEventStream } from "@/hooks/useEventStream";
import { useRunController } from "@/hooks/useRunController";
import { getThreadEvents, getThreadState, getThreadStateDb } from "@/lib/api/client";
import { EventUiState, initialEventUiState, reduceWithEvent } from "@/lib/events/reducer";
import { GraphNodeData, Strategy, StreamEvent } from "@/lib/types";

function prettyJson(value: unknown): string {
  return JSON.stringify(value ?? {}, null, 2);
}

function parseAssistantSummary(state: Record<string, unknown> | null): string {
  if (!state) return "";
  const finalOutput = state.final_output as Record<string, unknown> | undefined;
  if (finalOutput && typeof finalOutput.summary === "string") return finalOutput.summary;
  if (typeof state.summary === "string") return state.summary;
  return "";
}

export default function HomePage() {
  const [strategy, setStrategy] = useState<Strategy>("deep");
  const [maxConcurrency, setMaxConcurrency] = useState<number>(3);
  const [maxTasks, setMaxTasks] = useState<number>(6);
  const [eventUi, setEventUi] = useState(initialEventUiState);
  const [stateDbSnapshot, setStateDbSnapshot] = useState<Record<string, unknown> | null>(null);
  const [streamEnabled, setStreamEnabled] = useState(false);
  const [selectedNodeId, setSelectedNodeId] = useState<string | null>(null);
  const [expandedState, setExpandedState] = useState(false);
  const [expandedStateDb, setExpandedStateDb] = useState(false);

  const {
    threadId,
    threadOptions,
    messages,
    stateView,
    error: chatError,
    setError: setChatError,
    createThread,
    switchThread,
    addUserMessage,
    setAssistantRunning,
    resolveAssistantMessage,
    setStateView
  } = useChatThread();

  const { run, isRunning, error: runError, setError: setRunError } = useRunController();

  const handleEvent = useCallback(
    async (event: StreamEvent) => {
      setEventUi((prev) => reduceWithEvent(prev, event));

      if (event.type === "WORKFLOW_COMPLETED") {
        setStreamEnabled(false);
        const state = await getThreadState(threadId);
        setStateView(state.state || null);
        resolveAssistantMessage(parseAssistantSummary(state.state || null));
      }

      if (event.type === "WORKFLOW_FAILED") {
        setStreamEnabled(false);
        resolveAssistantMessage("运行失败，请查看错误日志。", true);
      }
    },
    [resolveAssistantMessage, setStateView, threadId]
  );

  const connectionStatus = useEventStream({
    threadId,
    enabled: streamEnabled,
    getSinceSeq: () => eventUi.lastSeq,
    onEvent: (event) => {
      void handleEvent(event);
    }
  });

  const hydrateThread = useCallback(async (nextThreadId: string) => {
    try {
      const eventsPayload = await getThreadEvents(nextThreadId, 0, 300);
      const items = Array.isArray(eventsPayload.events) ? eventsPayload.events : [];
      const next = items.reduce<EventUiState>((state, item) => {
        const maybeEvent = item as StreamEvent;
        if (typeof maybeEvent.type !== "string" || typeof maybeEvent.seq !== "number" || typeof maybeEvent.stream_id !== "string") {
          return state;
        }
        return reduceWithEvent(state, maybeEvent);
      }, initialEventUiState);
      setEventUi(next);
    } catch {
      setEventUi(initialEventUiState);
    }

    try {
      const stateDb = await getThreadStateDb(nextThreadId);
      setStateDbSnapshot(stateDb.state || null);
    } catch {
      setStateDbSnapshot(null);
    }
  }, []);

  useEffect(() => {
    if (!threadId) return;
    void switchThread(threadId);
    void hydrateThread(threadId);
  }, [hydrateThread, switchThread, threadId]);

  useEffect(() => {
    if (eventUi.phase !== "running" || !threadId) return;

    const timer = window.setInterval(async () => {
      try {
        const [state, stateDb] = await Promise.all([getThreadState(threadId), getThreadStateDb(threadId)]);
        setStateView(state.state || null);
        setStateDbSnapshot(stateDb.state || null);
      } catch {
        return;
      }
    }, 1500);

    return () => {
      window.clearInterval(timer);
    };
  }, [eventUi.phase, setStateView, threadId]);

  const onSend = useCallback(
    async (content: string) => {
      if (!threadId) return;
      setChatError("");
      setRunError("");
      addUserMessage(content);
      setAssistantRunning();
      setEventUi({ ...initialEventUiState, phase: "running" });
      setStreamEnabled(true);

      const runResult = await run({
        thread_id: threadId,
        user_request: content,
        strategy,
        max_concurrency: maxConcurrency,
        max_tasks: maxTasks
      });

      // 后端返回 202 Accepted，工作流已在后台启动
      // 完成/失败由 SSE 事件（WORKFLOW_COMPLETED/FAILED）触发 handleEvent 处理
      if (!runResult.accepted) {
        setStreamEnabled(false);
        setEventUi((prev) => ({ ...prev, phase: "failed" }));
        resolveAssistantMessage("请求提交失败，请检查服务连接。", true);
      }
    },
    [addUserMessage, maxConcurrency, maxTasks, resolveAssistantMessage, run, setAssistantRunning, setChatError, setRunError, strategy, threadId]
  );

  const selectedNode = useMemo<Node<GraphNodeData> | null>(() => {
    if (!selectedNodeId) return null;
    return eventUi.nodes.find((node) => node.id === selectedNodeId) || null;
  }, [eventUi.nodes, selectedNodeId]);

  const currentError = chatError || runError;

  return (
    <main className="chat-page">
      <section className="chat-column panel">
        <header className="chat-header">
          <h1>Shannon Chat Console</h1>
          <RunStatus phase={eventUi.phase} connectionStatus={connectionStatus} />
        </header>

        <div className="thread-toolbar">
          <select
            aria-label="thread-select"
            value={threadId}
            onChange={(event) => {
              const nextThread = event.target.value;
              setStreamEnabled(false);
              setEventUi(initialEventUiState);
              void switchThread(nextThread);
              void hydrateThread(nextThread);
            }}
          >
            {threadOptions.map((item) => (
              <option value={item} key={item}>
                {item}
              </option>
            ))}
          </select>
          <button
            type="button"
            onClick={() => {
              createThread();
              setEventUi(initialEventUiState);
              setStreamEnabled(false);
            }}
          >
            新建 Thread
          </button>
          <select aria-label="strategy-select" value={strategy} onChange={(e) => setStrategy(e.target.value as Strategy)}>
            <option value="quick">quick</option>
            <option value="standard">standard</option>
            <option value="deep">deep</option>
            <option value="academic">academic</option>
          </select>
          <input
            aria-label="max-concurrency"
            type="number"
            min={1}
            max={16}
            value={maxConcurrency}
            onChange={(event) => setMaxConcurrency(Number(event.target.value || 1))}
          />
          <input
            aria-label="max-tasks"
            type="number"
            min={1}
            max={30}
            value={maxTasks}
            onChange={(event) => setMaxTasks(Number(event.target.value || 1))}
          />
        </div>

        <MessageList messages={messages} />
        <Composer disabled={isRunning || eventUi.phase === "running"} onSend={onSend} />

        {currentError ? <div className="error">{currentError}</div> : null}
      </section>

      <section className="graph-column panel">
        <GraphLegend phases={eventUi.phases} />
        <CallGraph nodes={eventUi.nodes} edges={eventUi.edges} onSelectNode={setSelectedNodeId} />
        <NodeDetails node={selectedNode} />

        <article className="event-log">
          <h3>事件日志</h3>
          {eventUi.events.length === 0 ? (
            <div className="empty-state">暂无事件</div>
          ) : (
            <ul className="log-list">
              {eventUi.events.map((item) => (
                <li key={`${item.seq}-${item.stream_id}`}>
                  [{item.seq}] {item.type}
                  {item.message ? ` - ${item.message}` : ""}
                </li>
              ))}
            </ul>
          )}
        </article>

        <article className="json-panels">
          <button type="button" className="json-toggle" onClick={() => setExpandedState((prev) => !prev)}>
            {expandedState ? "隐藏" : "查看"} /state JSON
          </button>
          {expandedState ? <pre>{prettyJson(stateView)}</pre> : null}

          <button type="button" className="json-toggle" onClick={() => setExpandedStateDb((prev) => !prev)}>
            {expandedStateDb ? "隐藏" : "查看"} /state_db JSON
          </button>
          {expandedStateDb ? <pre>{prettyJson(stateDbSnapshot)}</pre> : null}
        </article>
      </section>
    </main>
  );
}
