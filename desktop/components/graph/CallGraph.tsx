"use client";

import "@xyflow/react/dist/style.css";
import { useEffect, useState } from "react";
import { Background, Controls, Edge, MiniMap, Node, ReactFlow } from "@xyflow/react";
import { GraphNodeData } from "@/lib/types";

interface CallGraphProps {
  nodes: Node<GraphNodeData>[];
  edges: Edge[];
  onSelectNode: (nodeId: string | null) => void;
}

export function CallGraph({ nodes, edges, onSelectNode }: CallGraphProps) {
  const [showMiniMap, setShowMiniMap] = useState(true);

  useEffect(() => {
    const mql = window.matchMedia("(max-width: 1000px)");
    const handler = (e: MediaQueryListEvent | MediaQueryList) => setShowMiniMap(!e.matches);
    handler(mql);
    mql.addEventListener("change", handler);
    return () => mql.removeEventListener("change", handler);
  }, []);

  if (!nodes.length) {
    return <div className="empty-state">等待事件生成调用图…</div>;
  }

  return (
    <div className="graph-canvas" aria-label="call-graph">
      <ReactFlow
        nodes={nodes}
        edges={edges}
        fitView
        onNodeClick={(_, node) => onSelectNode(node.id)}
        onPaneClick={() => onSelectNode(null)}
      >
        <Background />
        {showMiniMap && <MiniMap />}
        <Controls />
      </ReactFlow>
    </div>
  );
}
