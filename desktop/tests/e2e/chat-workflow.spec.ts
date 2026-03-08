import { expect, test } from "@playwright/test";

test("mock API + SSE completes one full chat workflow", async ({ page }) => {
  await page.route("**/api/runs", async (route) => {
    await route.fulfill({
      status: 202,
      contentType: "application/json",
      body: JSON.stringify({ thread_id: "thread-e2e", status: "accepted" })
    });
  });

  await page.route("**/api/threads/**/events?**", async (route) => {
    await route.fulfill({
      status: 200,
      contentType: "application/json",
      body: JSON.stringify({ events: [] })
    });
  });

  await page.route("**/api/threads/**/session", async (route) => {
    await route.fulfill({
      status: 200,
      contentType: "application/json",
      body: JSON.stringify({ thread_id: "thread-e2e", session: { messages: [] } })
    });
  });

  await page.route("**/api/threads/**/state-db", async (route) => {
    await route.fulfill({ status: 200, contentType: "application/json", body: JSON.stringify({ thread_id: "thread-e2e", state: {} }) });
  });

  await page.route("**/api/threads/**/state", async (route) => {
    await route.fulfill({
      status: 200,
      contentType: "application/json",
      body: JSON.stringify({ thread_id: "thread-e2e", state: { final_output: { summary: "E2E assistant summary" } } })
    });
  });

  await page.route("**/api/threads/**/events/stream?**", async (route) => {
    const body = [
      'data: {"type":"WORKFLOW_STARTED","seq":1,"stream_id":"w1","timestamp":1700000000,"payload":{}}\n\n',
      'data: {"type":"AGENT_CALL_STARTED","seq":2,"stream_id":"w2","timestamp":1700000001,"payload":{"from_agent":"orchestrator","to_agent":"research_agent","task_id":"task-1"}}\n\n',
      'data: {"type":"WORKFLOW_COMPLETED","seq":3,"stream_id":"w3","timestamp":1700000002,"payload":{}}\n\n'
    ].join("");

    await route.fulfill({
      status: 200,
      contentType: "text/event-stream",
      body,
      headers: {
        "cache-control": "no-cache"
      }
    });
  });

  await page.goto("/");
  await page.getByLabel("composer-input").fill("请执行流程");
  await page.getByRole("button", { name: "发送" }).click();

  await expect(page.getByText("WORKFLOW_STARTED")).toBeVisible();
  await expect(page.getByText("E2E assistant summary")).toBeVisible();
  await expect(page.getByText("task-1")).toBeVisible();
});

test("reconnects SSE with since_seq resume", async ({ page }) => {
  let streamCallCount = 0;
  let resumedWithSinceSeq = false;

  await page.route("**/api/runs", async (route) => {
    await route.fulfill({
      status: 202,
      contentType: "application/json",
      body: JSON.stringify({ thread_id: "thread-e2e", status: "accepted" })
    });
  });

  await page.route("**/api/threads/**/events?**", async (route) => {
    await route.fulfill({ status: 200, contentType: "application/json", body: JSON.stringify({ events: [] }) });
  });

  await page.route("**/api/threads/**/session", async (route) => {
    await route.fulfill({ status: 200, contentType: "application/json", body: JSON.stringify({ thread_id: "thread-e2e", session: { messages: [] } }) });
  });

  await page.route("**/api/threads/**/state", async (route) => {
    await route.fulfill({
      status: 200,
      contentType: "application/json",
      body: JSON.stringify({ thread_id: "thread-e2e", state: { final_output: { summary: "Reconnect completed" } } })
    });
  });

  await page.route("**/api/threads/**/state-db", async (route) => {
    await route.fulfill({ status: 200, contentType: "application/json", body: JSON.stringify({ thread_id: "thread-e2e", state: {} }) });
  });

  await page.route("**/api/threads/**/events/stream?**", async (route) => {
    streamCallCount += 1;
    const url = route.request().url();

    if (streamCallCount === 1) {
      await route.fulfill({
        status: 200,
        contentType: "text/event-stream",
        body: 'data: {"type":"WORKFLOW_STARTED","seq":1,"stream_id":"r1","timestamp":1700000000,"payload":{}}\n\n'
      });
      return;
    }

    if (url.includes("since_seq=1")) {
      resumedWithSinceSeq = true;
    }

    await route.fulfill({
      status: 200,
      contentType: "text/event-stream",
      body: 'data: {"type":"WORKFLOW_COMPLETED","seq":2,"stream_id":"r2","timestamp":1700000002,"payload":{}}\n\n'
    });
  });

  await page.goto("/");
  await page.getByLabel("composer-input").fill("断线重连测试");
  await page.getByRole("button", { name: "发送" }).click();

  await expect(page.getByText("Reconnect completed")).toBeVisible();
  await expect.poll(() => resumedWithSinceSeq).toBeTruthy();
});
