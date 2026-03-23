from __future__ import annotations

import argparse
import json
import re
import time
import uuid
from pathlib import Path
from typing import Any, Dict, List
from urllib import error, request

import sys

# 允许从仓库根目录直接运行脚本：python deploy/scripts/paradigm_content_acceptance.py
ROOT_DIR = Path(__file__).resolve().parents[2]
SRC_DIR = ROOT_DIR / "src"
if str(SRC_DIR) not in sys.path:
    sys.path.insert(0, str(SRC_DIR))

from shannon.quality.paradigm_testing import (
    evaluate_json_content,
    evaluate_report_content,
    infer_observed_mode,
    load_metrics_config,
    summarize_suite,
)

_JSON_BLOCK_RE = re.compile(r"```(?:json)?\s*(.*?)```", re.DOTALL | re.IGNORECASE)


def _http_json(method: str, url: str, payload: Dict[str, Any] | None = None, timeout: float = 30.0) -> Dict[str, Any]:
    data = None
    headers = {"Content-Type": "application/json"}
    if payload is not None:
        data = json.dumps(payload, ensure_ascii=False).encode("utf-8")
    req = request.Request(url=url, method=method, headers=headers, data=data)
    with request.urlopen(req, timeout=timeout) as resp:
        text = resp.read().decode("utf-8")
    parsed = json.loads(text) if text else {}
    if not isinstance(parsed, dict):
        raise ValueError(f"unexpected response type from {url}")
    return parsed


def _wait_for_run(base_url: str, thread_id: str, poll_interval: float, timeout_seconds: float) -> str:
    deadline = time.monotonic() + timeout_seconds
    last_status = "unknown"
    while time.monotonic() < deadline:
        try:
            payload = _http_json("GET", f"{base_url}/threads/{thread_id}/run_status")
            last_status = str(payload.get("run_status") or "unknown")
            if last_status in {"completed", "failed", "frozen"}:
                return last_status
        except Exception:
            pass
        time.sleep(poll_interval)
    return f"timeout:{last_status}"


def _parallel_peak_from_events(events: List[Dict[str, Any]]) -> int:
    max_peak = 0
    for event in events:
        if not isinstance(event, dict):
            continue
        payload = event.get("payload") if isinstance(event.get("payload"), dict) else {}
        if str(event.get("type") or "") == "NODE_STARTED" and str(payload.get("worker_count") or "").isdigit():
            max_peak = max(max_peak, int(payload.get("worker_count") or 0))
    return max_peak


def _extract_task_results(final_output: Dict[str, Any]) -> List[Dict[str, Any]]:
    items = final_output.get("task_results") if isinstance(final_output.get("task_results"), list) else []
    return [item for item in items if isinstance(item, dict)]


def _select_json_eval_content(summary: str, task_results: List[Dict[str, Any]]) -> tuple[str, str, str]:
    # Prefer raw task-jsonl payload for evaluation to avoid summary/file mismatch.
    for item in task_results:
        task_id = str(item.get("task_id") or "").strip()
        content = str(item.get("content") or "").strip()
        if not content:
            continue
        lower_task_id = task_id.lower()
        if lower_task_id == "task-jsonl" or "jsonl" in lower_task_id:
            return content, "task_result", task_id
    return summary, "summary", ""


def _extract_json_block(text: str) -> str:
    raw = str(text or "").strip()
    if not raw:
        return ""
    match = _JSON_BLOCK_RE.search(raw)
    if match:
        return match.group(1).strip()
    return raw


def _select_report_answer_content(summary: str, task_results: List[Dict[str, Any]]) -> tuple[str, str, str]:
    # Prefer merge/final task content as the final answer body for report mode.
    preferred_ids = ["task-merge", "task-summary", "task-final"]
    for tid in preferred_ids:
        for item in task_results:
            task_id = str(item.get("task_id") or "").strip().lower()
            content = str(item.get("content") or "").strip()
            if task_id == tid and content:
                return content, "task_result", str(item.get("task_id") or "")
    for item in task_results:
        task_id = str(item.get("task_id") or "").strip()
        content = str(item.get("content") or "").strip()
        if content:
            return content, "task_result", task_id
    return summary, "summary", ""


def _extract_token(final_output: Dict[str, Any]) -> tuple[float, str]:
    budget = final_output.get("budget") if isinstance(final_output.get("budget"), dict) else {}
    if budget and budget.get("used_token") is not None:
        try:
            return float(budget.get("used_token") or 0.0), "estimated"
        except Exception:
            return 0.0, "estimated"
    return 0.0, "estimated"


def _run_single_query(
    base_url: str,
    suite_id: str,
    query_row: Dict[str, Any],
    max_concurrency: int,
    max_tasks: int,
    poll_interval: float,
    timeout_seconds: float,
    report_cfg: Dict[str, Any],
) -> Dict[str, Any]:
    query_id = str(query_row.get("query_id") or f"{suite_id}-{uuid.uuid4().hex[:8]}")
    expected_mode = str(query_row.get("expected_mode") or "report")
    user_request = str(query_row.get("user_request") or "").strip()

    thread_id = f"suite-{suite_id}-{query_id}-{uuid.uuid4().hex[:6]}"
    start = time.monotonic()

    run_status = "failed_to_submit"
    state_payload: Dict[str, Any] = {"state": {}}
    events_payload: Dict[str, Any] = {"events": []}

    try:
        submit_timeout = max(30.0, min(float(timeout_seconds), 120.0))
        _http_json(
            "POST",
            f"{base_url}/runs",
            payload={
                "thread_id": thread_id,
                "user_request": user_request,
                "max_concurrency": max_concurrency,
                "max_tasks": max_tasks,
            },
            timeout=submit_timeout,
        )
        run_status = _wait_for_run(base_url, thread_id, poll_interval=poll_interval, timeout_seconds=timeout_seconds)
    except error.HTTPError as exc:
        run_status = f"submit_http_error:{exc.code}"
    except Exception as exc:  # noqa: BLE001
        run_status = f"submit_error:{type(exc).__name__}"

    end = time.monotonic()
    backend_latency_ms = round((end - start) * 1000.0, 2)

    try:
        state_payload = _http_json("GET", f"{base_url}/threads/{thread_id}/state")
    except Exception:
        state_payload = {"state": {}}

    try:
        events_payload = _http_json("GET", f"{base_url}/threads/{thread_id}/events?since_seq=0&limit=4000")
    except Exception:
        events_payload = {"events": []}

    state = state_payload.get("state") if isinstance(state_payload.get("state"), dict) else {}
    final_output = state.get("final_output") if isinstance(state.get("final_output"), dict) else {}

    summary = str(final_output.get("summary") or "").strip()
    task_results = _extract_task_results(final_output)

    observed_mode = infer_observed_mode(summary)
    classification_correct = observed_mode == expected_mode
    has_output = bool(summary)
    token_used_once, token_source = _extract_token(final_output)

    events = events_payload.get("events") if isinstance(events_payload.get("events"), list) else []
    parallel_agent_peak = _parallel_peak_from_events([item for item in events if isinstance(item, dict)])

    row: Dict[str, Any] = {
        "suite_id": suite_id,
        "query_id": query_id,
        "expected_mode": expected_mode,
        "observed_mode": observed_mode,
        "classification_correct": classification_correct,
        "has_output": has_output,
        "backend_latency_ms": backend_latency_ms,
        "parallel_agent_peak": parallel_agent_peak,
        "token_used_once": token_used_once,
        "token_source": token_source,
        "thread_id": thread_id,
        "run_status": run_status,
        "user_request": user_request,
        "final_summary_full": summary,
    }

    # Always expose extracted answer content aligned with expected mode.
    if expected_mode == "json_train":
        json_answer_text, json_answer_source, json_answer_task_id = _select_json_eval_content(summary, task_results)
        json_answer_text = _extract_json_block(json_answer_text)
        row["json_answer_full"] = json_answer_text
        row["json_answer_source"] = json_answer_source
        row["json_answer_task_id"] = json_answer_task_id
    else:
        report_answer_text, report_answer_source, report_answer_task_id = _select_report_answer_content(summary, task_results)
        row["report_answer_full"] = report_answer_text
        row["report_answer_source"] = report_answer_source
        row["report_answer_task_id"] = report_answer_task_id

    if observed_mode == "json_train":
        json_eval_content, json_eval_content_source, json_eval_task_id = _select_json_eval_content(summary, task_results)
        json_eval_content = _extract_json_block(json_eval_content)
        json_result = evaluate_json_content(
            content=json_eval_content,
            expected_count=int(query_row.get("expected_count") or 5),
            required_fields=[str(item) for item in (query_row.get("required_fields") or [])],
        )
        json_result["json_eval_content_source"] = json_eval_content_source
        json_result["json_eval_task_id"] = json_eval_task_id
        json_result["json_raw_content"] = json_eval_content
        json_result["json_answer_full"] = json_eval_content
        row.update(json_result)
        row.setdefault("report_gate_pass", False)
        row.setdefault("report_provisional_score", None)
    else:
        report_result = evaluate_report_content(
            content=summary,
            task_results=task_results,
            report_cfg=report_cfg,
        )
        report_result.setdefault("report_answer_full", row.get("report_answer_full", ""))
        row.update(report_result)
        row.setdefault("json_gate_pass", False)
        row.setdefault("json_schema_pass", False)

    return row


def _load_suite(path: Path) -> Dict[str, Any]:
    data = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        raise ValueError(f"invalid suite file: {path}")
    queries = data.get("queries") if isinstance(data.get("queries"), list) else []
    data["queries"] = [item for item in queries if isinstance(item, dict)]
    return data


def main() -> None:
    parser = argparse.ArgumentParser(description="Run paradigm content acceptance suites")
    parser.add_argument("--base-url", default="http://127.0.0.1:8000")
    parser.add_argument("--suite", choices=["report_set_a", "json_set_b", "all"], default="all")
    parser.add_argument("--max-concurrency", type=int, default=3)
    parser.add_argument("--max-tasks", type=int, default=8)
    parser.add_argument("--poll-interval", type=float, default=1.0)
    parser.add_argument("--timeout-seconds", type=float, default=900.0)
    parser.add_argument("--max-queries", type=int, default=0)
    parser.add_argument("--metrics-config", default="reports/content_quality/paradigm/config/metrics_v1.json")
    parser.add_argument("--report-suite", default="reports/content_quality/paradigm/suites/v1/report_set_a.json")
    parser.add_argument("--json-suite", default="reports/content_quality/paradigm/suites/v1/json_set_b.json")
    parser.add_argument("--output", default="reports/content_quality/paradigm/latest_report.json")
    args = parser.parse_args()

    metrics = load_metrics_config(args.metrics_config)
    report_cfg = metrics.get("report") if isinstance(metrics.get("report"), dict) else {}

    suite_paths: List[Path] = []
    if args.suite in {"report_set_a", "all"}:
        suite_paths.append(Path(args.report_suite))
    if args.suite in {"json_set_b", "all"}:
        suite_paths.append(Path(args.json_suite))

    started_at = time.time()
    suite_reports: List[Dict[str, Any]] = []
    all_records: List[Dict[str, Any]] = []

    for suite_path in suite_paths:
        suite_doc = _load_suite(suite_path)
        suite_id = str(suite_doc.get("suite_id") or suite_path.stem)
        max_queries = max(0, int(args.max_queries or 0))
        query_items = list(suite_doc.get("queries", []))
        if max_queries > 0:
            query_items = query_items[:max_queries]
        records: List[Dict[str, Any]] = []
        for query_row in query_items:
            record = _run_single_query(
                base_url=args.base_url,
                suite_id=suite_id,
                query_row=query_row,
                max_concurrency=max(1, int(args.max_concurrency)),
                max_tasks=max(1, int(args.max_tasks)),
                poll_interval=max(0.2, float(args.poll_interval)),
                timeout_seconds=max(60.0, float(args.timeout_seconds)),
                report_cfg=report_cfg,
            )
            records.append(record)

        suite_summary = summarize_suite(records)
        suite_reports.append(
            {
                "suite_id": suite_id,
                "version": str(suite_doc.get("version") or "v1"),
                "record_count": len(records),
                "summary": suite_summary,
                "records": records,
            }
        )
        all_records.extend(records)

    payload = {
        "generated_at": time.time(),
        "started_at": started_at,
        "metrics_version": str(metrics.get("version") or "v1"),
        "suites": suite_reports,
        "overall_summary": summarize_suite(all_records),
    }

    output_path = Path(args.output)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"paradigm content acceptance done, output={output_path}")


if __name__ == "__main__":
    main()
