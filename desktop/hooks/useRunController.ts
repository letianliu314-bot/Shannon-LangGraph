"use client";

import { useCallback, useState } from "react";
import { ApiError, postRun } from "@/lib/api/client";
import { RunRequest } from "@/lib/types";

interface RunResult {
  accepted: boolean;
}

export function useRunController() {
  const [isRunning, setIsRunning] = useState(false);
  const [error, setError] = useState<string>("");

  const run = useCallback(async (payload: RunRequest): Promise<RunResult> => {
    setError("");
    setIsRunning(true);
    try {
      await postRun(payload);
      // 后端返回 202 Accepted，工作流在后台执行
      // 前端通过 SSE 事件流获取完成/失败通知
      return { accepted: true };
    } catch (err) {
      const msg = err instanceof Error ? err.message : String(err);
      // 409 表示该 thread 已有运行中的工作流
      if (err instanceof ApiError && err.status === 409) {
        setError("该 Thread 已有运行中的任务，请等待完成或新建 Thread");
      } else {
        setError(msg);
      }
      return { accepted: false };
    } finally {
      setIsRunning(false);
    }
  }, []);

  return {
    run,
    isRunning,
    error,
    setError
  };
}
