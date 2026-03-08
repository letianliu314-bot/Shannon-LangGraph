"use client";

import { PhaseStatusMap, GraphNodeData } from "@/lib/types";

const statusItems: { label: string; className: string }[] = [
  { label: "running", className: "legend-running" },
  { label: "completed", className: "legend-completed" },
  { label: "failed", className: "legend-failed" },
  { label: "blocked", className: "legend-blocked" }
];

const phaseOrder = ["refine", "decompose", "schedule", "execute", "verify", "finalize"];
const phaseLabels: Record<string, string> = {
  refine: "精炼",
  decompose: "分解",
  schedule: "调度",
  execute: "执行",
  verify: "验证",
  finalize: "汇总"
};

const dotColor: Record<GraphNodeData["status"], string> = {
  idle: "#a9b4be",
  running: "#2563eb",
  completed: "#16a34a",
  failed: "#dc2626",
  blocked: "#ca8a04"
};

interface GraphLegendProps {
  phases?: PhaseStatusMap;
}

export function GraphLegend({ phases = {} }: GraphLegendProps) {
  return (
    <div className="legend-wrap">
      <div className="legend-title">工作流进度</div>
      <div className="legend-phases">
        {phaseOrder.map((phase, i) => {
          const status = phases[phase] || "idle";
          return (
            <span key={phase} className="legend-phase-item">
              {i > 0 && <span className="legend-phase-arrow">→</span>}
              <span
                className="legend-phase-dot"
                style={{
                  display: "inline-block",
                  width: 8,
                  height: 8,
                  borderRadius: "50%",
                  backgroundColor: dotColor[status],
                  marginRight: 4,
                  animation: status === "running" ? "pulse 1.2s infinite" : undefined
                }}
              />
              <span style={{ opacity: status === "idle" ? 0.5 : 1, fontWeight: status === "running" ? 600 : 400 }}>
                {phaseLabels[phase]}
              </span>
            </span>
          );
        })}
      </div>
      <div className="legend-items">
        {statusItems.map((item) => (
          <span key={item.label} className={`legend-item ${item.className}`}>
            {item.label}
          </span>
        ))}
      </div>
    </div>
  );
}
