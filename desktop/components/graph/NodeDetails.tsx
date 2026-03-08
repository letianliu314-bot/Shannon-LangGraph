"use client";

import { Node } from "@xyflow/react";
import { GraphNodeData } from "@/lib/types";

interface NodeDetailsProps {
  node: Node<GraphNodeData> | null;
}

export function NodeDetails({ node }: NodeDetailsProps) {
  if (!node) {
    return <div className="empty-state">点击图中节点查看详情。</div>;
  }

  const d = node.data;

  return (
    <div className="node-detail" aria-label="node-details">
      <h3>{d.label}</h3>
      <dl>
        <dt>类型</dt>
        <dd>{d.kind}</dd>
        {d.taskId && (
          <>
            <dt>task_id</dt>
            <dd>{d.taskId}</dd>
          </>
        )}
        {d.eventType && (
          <>
            <dt>事件类型</dt>
            <dd>{d.eventType}</dd>
          </>
        )}
        {d.fromAgent && (
          <>
            <dt>from_agent</dt>
            <dd>{d.fromAgent}</dd>
          </>
        )}
        {d.toAgent && (
          <>
            <dt>to_agent</dt>
            <dd>{d.toAgent}</dd>
          </>
        )}
        <dt>状态</dt>
        <dd>{d.status}</dd>
        <dt>时间</dt>
        <dd>{d.timestamp ? new Date(d.timestamp * 1000).toLocaleString() : "-"}</dd>
        {d.error && (
          <>
            <dt>错误</dt>
            <dd style={{ color: "var(--danger)" }}>{d.error}</dd>
          </>
        )}
      </dl>
    </div>
  );
}
