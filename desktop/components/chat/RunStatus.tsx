"use client";

import { ConnectionStatus, RunPhase } from "@/lib/types";

interface RunStatusProps {
  phase: RunPhase;
  connectionStatus: ConnectionStatus;
}

export function RunStatus({ phase, connectionStatus }: RunStatusProps) {
  return (
    <div className="run-status-wrap">
      <span className={`status-pill ${phase}`}>run: {phase}</span>
      <span className={`status-pill ${connectionStatus}`}>sse: {connectionStatus}</span>
    </div>
  );
}
