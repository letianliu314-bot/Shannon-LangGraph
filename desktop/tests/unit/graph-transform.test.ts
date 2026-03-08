import { describe, expect, it } from "vitest";
import { buildGraphFromEvents } from "@/lib/events/graph";
import { StreamEvent } from "@/lib/types";

/* ── 辅助工厂 ── */

function evt(
  type: string,
  seq: number,
  payload: Record<string, unknown> = {},
  extra: Partial<StreamEvent> = {}
): StreamEvent {
  return { type, seq, stream_id: `s${seq}`, timestamp: 1700000000 + seq, payload, ...extra };
}

/* ── 测试用例 ── */

describe("graph transform – three-layer structure", () => {
  it("creates root node even with no events", () => {
    const { nodes, edges } = buildGraphFromEvents([]);
    expect(nodes).toHaveLength(1);
    expect(nodes[0].id).toBe("root");
    expect(nodes[0].data.kind).toBe("root");
    expect(nodes[0].data.status).toBe("idle");
    expect(edges).toHaveLength(0);
  });

  it("WORKFLOW_STARTED activates root to running", () => {
    const { nodes } = buildGraphFromEvents([evt("WORKFLOW_STARTED", 1)]);
    const root = nodes.find((n) => n.id === "root")!;
    expect(root.data.status).toBe("running");
  });

  it("creates task nodes from AGENT_CALL events hanging off root", () => {
    const { nodes, edges } = buildGraphFromEvents([
      evt("WORKFLOW_STARTED", 1),
      evt("AGENT_CALL_STARTED", 2, { from_agent: "orchestrator", to_agent: "llm_service", task_id: "task-1" }),
      evt("AGENT_CALL_STARTED", 3, { from_agent: "orchestrator", to_agent: "llm_service", task_id: "task-2" })
    ]);

    // root + 2 tasks = 3 nodes
    expect(nodes).toHaveLength(3);
    expect(nodes.some((n) => n.id === "task:task-1" && n.data.kind === "task")).toBe(true);
    expect(nodes.some((n) => n.id === "task:task-2" && n.data.kind === "task")).toBe(true);
    // 2 edges: root→task-1, root→task-2
    expect(edges).toHaveLength(2);
    expect(edges.every((e) => e.source === "root")).toBe(true);
  });

  it("full workflow produces three-layer structure: root → tasks → summary", () => {
    const { nodes, edges } = buildGraphFromEvents([
      evt("WORKFLOW_STARTED", 1),
      evt("AGENT_CALL_STARTED", 2, { task_id: "t1" }),
      evt("AGENT_CALL_STARTED", 3, { task_id: "t2" }),
      evt("AGENT_CALL_STARTED", 4, { task_id: "t3" }),
      evt("AGENT_CALL_COMPLETED", 5, { task_id: "t1" }),
      evt("AGENT_CALL_COMPLETED", 6, { task_id: "t2" }),
      evt("AGENT_CALL_COMPLETED", 7, { task_id: "t3" }),
      evt("WORKFLOW_COMPLETED", 8)
    ]);

    // root + 3 tasks + summary = 5 nodes
    expect(nodes).toHaveLength(5);
    expect(nodes.find((n) => n.id === "root")!.data.kind).toBe("root");
    expect(nodes.find((n) => n.id === "summary")!.data.kind).toBe("summary");
    expect(nodes.filter((n) => n.data.kind === "task")).toHaveLength(3);

    // 3 edges root→tasks + 3 edges tasks→summary = 6 edges
    expect(edges).toHaveLength(6);
    expect(edges.filter((e) => e.source === "root").length).toBe(3);
    expect(edges.filter((e) => e.target === "summary").length).toBe(3);
  });

  it("layer hierarchy: task y > root y, summary y > task y", () => {
    const { nodes } = buildGraphFromEvents([
      evt("WORKFLOW_STARTED", 1),
      evt("AGENT_CALL_STARTED", 2, { task_id: "t1" }),
      evt("AGENT_CALL_STARTED", 3, { task_id: "t2" }),
      evt("WORKFLOW_COMPLETED", 4)
    ]);

    const rootY = nodes.find((n) => n.id === "root")!.position.y;
    const summaryY = nodes.find((n) => n.id === "summary")!.position.y;
    const taskYs = nodes.filter((n) => n.data.kind === "task").map((n) => n.position.y);

    // All tasks below root
    for (const ty of taskYs) {
      expect(ty).toBeGreaterThan(rootY);
    }
    // Summary below all tasks
    for (const ty of taskYs) {
      expect(summaryY).toBeGreaterThan(ty);
    }
    // Same-layer tasks have same y
    expect(new Set(taskYs).size).toBe(1);
  });

  it("task status updates with STARTED/COMPLETED/FAILED/BLOCKED", () => {
    const { nodes: n1 } = buildGraphFromEvents([
      evt("WORKFLOW_STARTED", 1),
      evt("AGENT_CALL_STARTED", 2, { task_id: "t1" })
    ]);
    expect(n1.find((n) => n.id === "task:t1")!.data.status).toBe("running");

    const { nodes: n2 } = buildGraphFromEvents([
      evt("WORKFLOW_STARTED", 1),
      evt("AGENT_CALL_STARTED", 2, { task_id: "t1" }),
      evt("AGENT_CALL_COMPLETED", 3, { task_id: "t1" })
    ]);
    expect(n2.find((n) => n.id === "task:t1")!.data.status).toBe("completed");

    const { nodes: n3 } = buildGraphFromEvents([
      evt("WORKFLOW_STARTED", 1),
      evt("AGENT_CALL_STARTED", 2, { task_id: "t1" }),
      evt("AGENT_CALL_FAILED", 3, { task_id: "t1" })
    ]);
    expect(n3.find((n) => n.id === "task:t1")!.data.status).toBe("failed");

    const { nodes: n4 } = buildGraphFromEvents([
      evt("WORKFLOW_STARTED", 1),
      evt("AGENT_BLOCKED", 2, { task_id: "t1" })
    ]);
    expect(n4.find((n) => n.id === "task:t1")!.data.status).toBe("blocked");
  });

  it("summary follows workflow terminal status", () => {
    const { nodes: nc } = buildGraphFromEvents([
      evt("WORKFLOW_STARTED", 1),
      evt("AGENT_CALL_STARTED", 2, { task_id: "t1" }),
      evt("WORKFLOW_COMPLETED", 3)
    ]);
    expect(nc.find((n) => n.id === "summary")!.data.status).toBe("completed");

    const { nodes: nf } = buildGraphFromEvents([
      evt("WORKFLOW_STARTED", 1),
      evt("AGENT_CALL_STARTED", 2, { task_id: "t1" }),
      evt("WORKFLOW_FAILED", 3)
    ]);
    expect(nf.find((n) => n.id === "summary")!.data.status).toBe("failed");
  });

  it("parent_task_id creates hierarchical edge instead of root edge", () => {
    const { nodes, edges } = buildGraphFromEvents([
      evt("WORKFLOW_STARTED", 1),
      evt("AGENT_CALL_STARTED", 2, { task_id: "parent" }),
      evt("AGENT_CALL_STARTED", 3, { task_id: "child", parent_task_id: "parent" }),
      evt("WORKFLOW_COMPLETED", 4)
    ]);

    // root + parent + child + summary = 4 nodes
    expect(nodes).toHaveLength(4);
    // Edges: root→parent, parent→child, child→summary (leaf)
    expect(edges.some((e) => e.source === "task:parent" && e.target === "task:child")).toBe(true);
    expect(edges.some((e) => e.source === "root" && e.target === "task:parent")).toBe(true);
    // parent is NOT a leaf → no edge parent→summary
    expect(edges.some((e) => e.source === "task:parent" && e.target === "summary")).toBe(false);
    // child IS a leaf → edge child→summary
    expect(edges.some((e) => e.source === "task:child" && e.target === "summary")).toBe(true);
  });

  it("phases are extracted but not added as graph nodes", () => {
    const { nodes, phases } = buildGraphFromEvents([
      evt("NODE_STARTED", 1, { node: "refine" }),
      evt("NODE_COMPLETED", 2, { node: "refine" }),
      evt("NODE_STARTED", 3, { node: "decompose" })
    ]);

    // No phase nodes in graph
    expect(nodes.every((n) => n.data.kind !== ("phase" as string))).toBe(true);
    // Phase statuses are extracted
    expect(phases.refine).toBe("completed");
    expect(phases.decompose).toBe("running");
  });

  it("edges have no labels (clean visual)", () => {
    const { edges } = buildGraphFromEvents([
      evt("WORKFLOW_STARTED", 1),
      evt("AGENT_CALL_STARTED", 2, { task_id: "t1" }),
      evt("WORKFLOW_COMPLETED", 3)
    ]);

    for (const edge of edges) {
      expect(edge.label).toBeUndefined();
    }
  });

  it("workflow completed with no tasks: root connects directly to summary", () => {
    const { nodes, edges } = buildGraphFromEvents([
      evt("WORKFLOW_STARTED", 1),
      evt("WORKFLOW_COMPLETED", 2)
    ]);

    expect(nodes).toHaveLength(2); // root + summary
    expect(edges).toHaveLength(1);
    expect(edges[0].source).toBe("root");
    expect(edges[0].target).toBe("summary");
  });
});
