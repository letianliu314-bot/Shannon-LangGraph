"use client";

import { useEffect, useRef, useState } from "react";
import { ConnectionStatus, StreamEvent } from "@/lib/types";

interface UseEventStreamOptions {
  threadId: string;
  enabled: boolean;
  getSinceSeq: () => number;
  onEvent: (event: StreamEvent) => void;
  maxRetries?: number;
}

export function useEventStream({
  threadId,
  enabled,
  getSinceSeq,
  onEvent,
  maxRetries = 8
}: UseEventStreamOptions): ConnectionStatus {
  const [status, setStatus] = useState<ConnectionStatus>("disconnected");
  const retriesRef = useRef(0);
  const sourceRef = useRef<EventSource | null>(null);
  const reconnectTimerRef = useRef<number | null>(null);
  const onEventRef = useRef(onEvent);
  const getSinceSeqRef = useRef(getSinceSeq);

  useEffect(() => {
    onEventRef.current = onEvent;
  }, [onEvent]);

  useEffect(() => {
    getSinceSeqRef.current = getSinceSeq;
  }, [getSinceSeq]);

  useEffect(() => {
    if (!enabled || !threadId) {
      setStatus("disconnected");
      sourceRef.current?.close();
      sourceRef.current = null;
      return;
    }

    let stopped = false;

    const clearReconnect = () => {
      if (reconnectTimerRef.current) {
        window.clearTimeout(reconnectTimerRef.current);
        reconnectTimerRef.current = null;
      }
    };

    const connect = () => {
      const sinceSeq = getSinceSeqRef.current();
      const source = new EventSource(`/api/threads/${encodeURIComponent(threadId)}/events/stream?since_seq=${sinceSeq}`);
      sourceRef.current = source;

      source.onopen = () => {
        retriesRef.current = 0;
        setStatus("connected");
      };

      source.onmessage = (message) => {
        try {
          const parsed = JSON.parse(message.data) as StreamEvent;
          onEventRef.current(parsed);
        } catch {
          setStatus("reconnecting");
        }
      };

      source.onerror = () => {
        source.close();
        if (stopped) {
          return;
        }

        retriesRef.current += 1;
        if (retriesRef.current > maxRetries) {
          setStatus("disconnected");
          return;
        }

        setStatus("reconnecting");
        const delay = Math.min(10_000, 500 * 2 ** (retriesRef.current - 1));
        clearReconnect();
        reconnectTimerRef.current = window.setTimeout(connect, delay);
      };
    };

    connect();

    return () => {
      stopped = true;
      clearReconnect();
      sourceRef.current?.close();
      sourceRef.current = null;
    };
  }, [enabled, maxRetries, threadId]);

  return status;
}
