"use client";

import { useCallback, useEffect, useMemo, useState } from "react";
import { getThreadSession, getThreadState } from "@/lib/api/client";
import { ChatMessage } from "@/lib/types";

const THREAD_STORAGE_KEY = "shannon:threads";

function generateThreadId(): string {
  return `thread-${Date.now()}`;
}

function parseAssistantSummary(state: Record<string, unknown> | null): string {
  if (!state) return "";

  const finalOutput = state.final_output as Record<string, unknown> | undefined;
  if (finalOutput && typeof finalOutput.summary === "string") {
    return finalOutput.summary;
  }

  if (typeof state.summary === "string") {
    return state.summary;
  }

  return "";
}

function normalizeSessionMessages(session: Record<string, unknown> | undefined): ChatMessage[] {
  if (!session) return [];
  const rawMessages = Array.isArray(session.messages) ? session.messages : [];
  return rawMessages
    .map((item, index) => {
      const msg = item as Record<string, unknown>;
      const role = msg.role === "assistant" ? "assistant" : msg.role === "user" ? "user" : null;
      const content = typeof msg.content === "string" ? msg.content : "";
      if (!role || !content) return null;
      const ts = typeof msg.timestamp === "number" ? msg.timestamp : Date.now() + index;
      return {
        id: `${role}-${ts}-${index}`,
        role,
        content,
        timestamp: ts,
        status: role === "assistant" ? "completed" : undefined
      } as ChatMessage;
    })
    .filter((msg): msg is ChatMessage => Boolean(msg));
}

export function useChatThread() {
  const [threadId, setThreadId] = useState<string>("");
  const [threadOptions, setThreadOptions] = useState<string[]>([]);
  const [messagesByThread, setMessagesByThread] = useState<Record<string, ChatMessage[]>>({});
  const [stateView, setStateView] = useState<Record<string, unknown> | null>(null);
  const [error, setError] = useState<string>("");

  useEffect(() => {
    const saved = typeof window !== "undefined" ? localStorage.getItem(THREAD_STORAGE_KEY) : null;
    const parsed = saved ? (JSON.parse(saved) as string[]) : [];
    const initial = parsed.length ? parsed : [generateThreadId()];
    setThreadOptions(initial);
    setThreadId(initial[0]);
  }, []);

  useEffect(() => {
    if (!threadOptions.length) return;
    localStorage.setItem(THREAD_STORAGE_KEY, JSON.stringify(threadOptions));
  }, [threadOptions]);

  const messages = useMemo(() => messagesByThread[threadId] ?? [], [messagesByThread, threadId]);

  const appendThread = useCallback((nextThreadId: string) => {
    setThreadOptions((prev) => (prev.includes(nextThreadId) ? prev : [nextThreadId, ...prev]));
  }, []);

  const createThread = useCallback(() => {
    const next = generateThreadId();
    appendThread(next);
    setThreadId(next);
    setError("");
  }, [appendThread]);

  const switchThread = useCallback(
    async (nextThreadId: string) => {
      setThreadId(nextThreadId);
      setError("");
      appendThread(nextThreadId);

      try {
        const [session, state] = await Promise.all([
          getThreadSession(nextThreadId).catch(() => ({ thread_id: nextThreadId, session: {} })),
          getThreadState(nextThreadId).catch(() => ({ thread_id: nextThreadId, state: {} }))
        ]);

        const normalized = normalizeSessionMessages(session.session);
        const summary = parseAssistantSummary(state.state || null);

        setMessagesByThread((prev) => {
          const existing = prev[nextThreadId] ?? [];
          const merged = normalized.length ? normalized : existing;
          if (summary && !merged.some((item) => item.role === "assistant" && item.content === summary)) {
            return {
              ...prev,
              [nextThreadId]: [
                ...merged,
                {
                  id: `assistant-summary-${Date.now()}`,
                  role: "assistant",
                  content: summary,
                  timestamp: Date.now(),
                  status: "completed"
                }
              ]
            };
          }

          return {
            ...prev,
            [nextThreadId]: merged
          };
        });

        setStateView(state.state || null);
      } catch (err) {
        setError(err instanceof Error ? err.message : String(err));
      }
    },
    [appendThread]
  );

  const addUserMessage = useCallback((content: string) => {
    const message: ChatMessage = {
      id: `user-${Date.now()}`,
      role: "user",
      content,
      timestamp: Date.now()
    };
    setMessagesByThread((prev) => ({
      ...prev,
      [threadId]: [...(prev[threadId] ?? []), message]
    }));
  }, [threadId]);

  const setAssistantRunning = useCallback(() => {
    setMessagesByThread((prev) => ({
      ...prev,
      [threadId]: [
        ...(prev[threadId] ?? []).filter((msg) => msg.id !== "assistant-running"),
        {
          id: "assistant-running",
          role: "assistant",
          content: "正在处理中…",
          timestamp: Date.now(),
          status: "running"
        }
      ]
    }));
  }, [threadId]);

  const resolveAssistantMessage = useCallback((content: string, failed = false) => {
    if (!content && !failed) return;
    setMessagesByThread((prev) => {
      const next = (prev[threadId] ?? []).filter((msg) => msg.id !== "assistant-running");
      return {
        ...prev,
        [threadId]: [
          ...next,
          {
            id: `assistant-${Date.now()}`,
            role: "assistant",
            content: content || "运行失败，请查看事件日志。",
            timestamp: Date.now(),
            status: failed ? "failed" : "completed"
          }
        ]
      };
    });
  }, [threadId]);

  return {
    threadId,
    threadOptions,
    messages,
    stateView,
    error,
    setError,
    createThread,
    switchThread,
    addUserMessage,
    setAssistantRunning,
    resolveAssistantMessage,
    setStateView
  };
}
