from __future__ import annotations

import json
import re
import statistics
from typing import Any, Dict, List, Tuple

_JSON_BLOCK_RE = re.compile(r"```(?:json)?\s*(.*?)```", re.DOTALL | re.IGNORECASE)
_URL_RE = re.compile(r"https?://[^\s)\]>\"']+")


def load_metrics_config(path: str) -> Dict[str, Any]:
    with open(path, "r", encoding="utf-8") as f:
        data = json.load(f)
    if not isinstance(data, dict):
        raise ValueError("metrics config must be a JSON object")
    return data


def _strip_json_fence(text: str) -> str:
    match = _JSON_BLOCK_RE.search(text)
    if match:
        return match.group(1).strip()
    return text.strip()


def parse_json_records(text: str) -> Tuple[List[Dict[str, Any]], str]:
    raw = _strip_json_fence(str(text or ""))
    if not raw:
        return [], "empty_output"

    # 1) JSON array or single object
    try:
        parsed = json.loads(raw)
        if isinstance(parsed, list):
            if all(isinstance(item, dict) for item in parsed):
                return parsed, ""
            return [], "json_list_contains_non_object"
        if isinstance(parsed, dict):
            if isinstance(parsed.get("items"), list) and all(isinstance(item, dict) for item in parsed["items"]):
                return parsed["items"], ""
            return [parsed], ""
    except Exception:
        pass

    # 2) JSONL lines
    lines = [line.strip() for line in raw.splitlines() if line.strip()]
    if not lines:
        return [], "empty_output"

    rows: List[Dict[str, Any]] = []
    for idx, line in enumerate(lines, start=1):
        try:
            row = json.loads(line)
        except Exception:
            return [], f"invalid_jsonl_line_{idx}"
        if not isinstance(row, dict):
            return [], f"jsonl_line_{idx}_not_object"
        rows.append(row)
    return rows, ""


def infer_observed_mode(content: str) -> str:
    rows, error = parse_json_records(content)
    if not error and rows:
        return "json_train"
    return "report"


def count_report_citations(content: str, task_results: List[Dict[str, Any]] | None = None) -> int:
    urls = set(_URL_RE.findall(str(content or "")))
    bracket_refs = len(re.findall(r"\[(\d{1,2})\]", str(content or "")))

    if isinstance(task_results, list):
        for item in task_results:
            citations = item.get("citations") if isinstance(item, dict) else None
            if isinstance(citations, list):
                for citation in citations:
                    if isinstance(citation, dict):
                        url = str(citation.get("url") or "").strip()
                        if url:
                            urls.add(url)

    return len(urls) + bracket_refs


def fluency_pass(content: str) -> bool:
    text = str(content or "").strip()
    if not text:
        return False
    if "I will continue searching" in text:
        return False
    if "[finalize-fallback]" in text:
        return False

    compact = re.sub(r"\s+", "", text)
    if len(compact) < 120:
        return False

    # Repetition guard: reject when a 16-char fragment repeats too often.
    if len(compact) >= 64:
        fragment = compact[:16]
        if fragment and compact.count(fragment) >= 4:
            return False

    return True


def evaluate_report_content(content: str, task_results: List[Dict[str, Any]] | None, report_cfg: Dict[str, Any]) -> Dict[str, Any]:
    gates = report_cfg.get("gates") if isinstance(report_cfg.get("gates"), dict) else {}
    scoring = report_cfg.get("scoring") if isinstance(report_cfg.get("scoring"), dict) else {}

    min_char_count = int(gates.get("min_char_count", 500) or 500)
    min_citation_count = int(gates.get("min_citation_count", 1) or 1)
    require_fluency = bool(gates.get("require_fluency_pass", True))

    text = str(content or "")
    char_count = len(re.sub(r"\s+", "", text))
    citation_count = count_report_citations(text, task_results)
    fluency_ok = fluency_pass(text)

    char_gate_pass = char_count >= min_char_count
    citation_gate_pass = citation_count >= min_citation_count
    fluency_gate_pass = (not require_fluency) or fluency_ok
    gate_pass = char_gate_pass and citation_gate_pass and fluency_gate_pass

    char_score_max = float(scoring.get("char_score_max", 60) or 60)
    char_score_full_at = float(scoring.get("char_score_full_at", 1200) or 1200)
    citation_score_max = float(scoring.get("citation_score_max", 40) or 40)
    citation_score_full_at = float(scoring.get("citation_score_full_at", 6) or 6)

    char_score = min(char_score_max, char_score_max * (char_count / max(char_score_full_at, 1.0)))
    citation_score = min(citation_score_max, citation_score_max * (citation_count / max(citation_score_full_at, 1.0)))
    provisional_score = round(char_score + citation_score, 2)

    fail_reasons: List[str] = []
    if not char_gate_pass:
        fail_reasons.append("report_too_short")
    if not citation_gate_pass:
        fail_reasons.append("citation_missing")
    if not fluency_gate_pass:
        fail_reasons.append("fluency_failed")

    return {
        "report_char_count": char_count,
        "report_citation_count": citation_count,
        "report_fluency_pass": fluency_ok,
        "report_gate_pass": gate_pass,
        "report_provisional_score": provisional_score,
        "fail_reasons": fail_reasons,
    }


def evaluate_json_content(content: str, expected_count: int, required_fields: List[str]) -> Dict[str, Any]:
    rows, parse_error = parse_json_records(content)
    fail_reasons: List[str] = []

    if parse_error:
        fail_reasons.append(parse_error)

    count_pass = (not parse_error) and len(rows) == int(expected_count)
    if not count_pass:
        fail_reasons.append("json_count_mismatch")

    required_set = {str(field).strip() for field in required_fields if str(field).strip()}
    fields_pass = True
    non_empty_pass = True
    if not parse_error:
        for row in rows:
            keys = set(row.keys())
            if not required_set.issubset(keys):
                fields_pass = False
            for field in required_set:
                value = row.get(field)
                if value is None or (isinstance(value, str) and not value.strip()):
                    non_empty_pass = False

    if not fields_pass:
        fail_reasons.append("required_fields_missing")
    if not non_empty_pass:
        fail_reasons.append("required_fields_empty")

    gate_pass = (not parse_error) and count_pass and fields_pass and non_empty_pass

    return {
        "json_item_count": len(rows),
        "json_schema_pass": gate_pass,
        "json_gate_pass": gate_pass,
        "json_required_fields": sorted(required_set),
        "fail_reasons": fail_reasons,
    }


def summarize_suite(records: List[Dict[str, Any]]) -> Dict[str, Any]:
    total = len(records)
    if total == 0:
        return {
            "total": 0,
            "classification_accuracy": 0.0,
            "has_output_rate": 0.0,
            "gate_pass_rate": 0.0,
            "latency_p50_ms": 0.0,
            "latency_p90_ms": 0.0,
            "token_avg": 0.0,
            "token_max": 0.0,
            "parallel_peak_max": 0,
        }

    correct = sum(1 for row in records if bool(row.get("classification_correct")))
    has_output = sum(1 for row in records if bool(row.get("has_output")))
    gate_pass = sum(
        1
        for row in records
        if bool(row.get("report_gate_pass")) or bool(row.get("json_gate_pass"))
    )

    latencies = [float(row.get("backend_latency_ms", 0.0) or 0.0) for row in records]
    tokens = [float(row.get("token_used_once", 0.0) or 0.0) for row in records]
    parallel_peaks = [int(row.get("parallel_agent_peak", 0) or 0) for row in records]

    lat_sorted = sorted(latencies)
    idx_p50 = min(len(lat_sorted) - 1, int(0.5 * (len(lat_sorted) - 1)))
    idx_p90 = min(len(lat_sorted) - 1, int(0.9 * (len(lat_sorted) - 1)))

    return {
        "total": total,
        "classification_accuracy": round(correct / total, 4),
        "has_output_rate": round(has_output / total, 4),
        "gate_pass_rate": round(gate_pass / total, 4),
        "latency_p50_ms": round(lat_sorted[idx_p50], 2),
        "latency_p90_ms": round(lat_sorted[idx_p90], 2),
        "token_avg": round(statistics.fmean(tokens), 2) if tokens else 0.0,
        "token_max": round(max(tokens), 2) if tokens else 0.0,
        "parallel_peak_max": max(parallel_peaks) if parallel_peaks else 0,
    }
