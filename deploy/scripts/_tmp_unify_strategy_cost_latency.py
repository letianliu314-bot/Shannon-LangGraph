import json
import time
import urllib.request
from pathlib import Path

base = "http://127.0.0.1:8000"
req_text = "Compare open-source and closed-source model strategy for a mid-size B2B SaaS in next 12 months"
runs = []


def post_json(url, payload):
    data = json.dumps(payload).encode("utf-8")
    req = urllib.request.Request(url, data=data, headers={"Content-Type": "application/json"}, method="POST")
    with urllib.request.urlopen(req, timeout=30) as resp:
        return json.loads(resp.read().decode("utf-8"))


def get_json(url):
    with urllib.request.urlopen(url, timeout=30) as resp:
        return json.loads(resp.read().decode("utf-8"))


for requested in ["quick", "deep"]:
    thread_id = f"unify-baseline-{requested}-{int(time.time()*1000)}"
    t0 = time.time()
    post_json(
        base + "/runs",
        {
            "thread_id": thread_id,
            "user_request": req_text,
            "strategy": requested,
            "max_tasks": 6,
            "max_concurrency": 3,
        },
    )

    status = "running"
    deadline = time.time() + 300
    while status in {"running", "unknown"} and time.time() < deadline:
        time.sleep(1)
        status_payload = get_json(base + f"/threads/{thread_id}/run_status")
        status = str(status_payload.get("run_status", "unknown"))

    elapsed = round(time.time() - t0, 3)
    state_payload = get_json(base + f"/threads/{thread_id}/state")
    state = state_payload.get("state") or {}
    final = state.get("final_output") or {}
    budget = final.get("budget") or {}

    runs.append(
        {
            "strategy_requested": requested,
            "thread_id": thread_id,
            "run_status": status,
            "elapsed_seconds": elapsed,
            "completed_task_count": int(final.get("completed_task_count", 0) or 0),
            "used_token": int(budget.get("used_token", 0) or 0),
        }
    )

report = {"generated_at": time.time(), "runs": runs}
out_path = Path("reports/content_quality/stress/unify_strategy_cost_latency.json")
out_path.parent.mkdir(parents=True, exist_ok=True)
out_path.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
print(json.dumps(report, ensure_ascii=False, indent=2))
