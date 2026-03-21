from __future__ import annotations

import json
import re
from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import Any, Dict, List, Tuple

from langgraph.graph import END, START, StateGraph

from shannon.orchestration.orchestrator.llm_service_client import LLMServiceClient
from shannon.orchestration.orchestrator.state import ResearchState, ResearchTask
from shannon.storage.memory_layer import shared_memory_store
from shannon.storage.redis.streaming_manager import Event
from shannon.storage.version_layer import git_version_store

# 中文注释：LangGraph 编排图实现（refine -> decompose -> schedule -> execute -> verify -> finalize）

_streaming_manager: Any = None


def set_streaming_manager(manager: Any) -> None:
    # 中文注释：注入运行时流式事件管理器，便于节点发布事件
    global _streaming_manager
    _streaming_manager = manager


def _resolve_thread_id(state: ResearchState) -> str:
    return str(state.get("thread_id") or "")


def _resolve_phase(state: ResearchState) -> str:
    return str(state.get("phase") or "phase-1")


def _emit_event(
    state: ResearchState,
    event_type: str,
    message: str,
    payload: Dict[str, Any] | None = None,
    node: str | None = None,
) -> None:
    # 中文注释：节点事件发布（失败不阻断主链路）
    if _streaming_manager is None:
        return
    thread_id = _resolve_thread_id(state)
    if not thread_id:
        return

    body = dict(payload or {})
    body.setdefault("run_id", thread_id)
    body.setdefault("phase", _resolve_phase(state))
    body.setdefault("gate_status", str(state.get("gate_status") or "unknown"))
    if node:
        body.setdefault("node", node)

    try:
        _streaming_manager.publish(
            thread_id,
            Event(
                workflow_id=thread_id,
                type=event_type,
                agent_id="orchestrator.graph",
                message=message,
                payload=body,
            ),
        )
    except Exception:
        pass


def _emit_agent_call(
    state: ResearchState,
    phase: str,
    from_agent: str,
    to_agent: str,
    call_name: str,
    node: str,
    task_id: str | None = None,
    role_preset: str | None = None,
    model_tier: str | None = None,
    status: str | None = None,
    error: str | None = None,
    extra: Dict[str, Any] | None = None,
) -> None:
    # 中文注释：统一发布 agent 间调用事件，便于前端展示调用顺序
    payload: Dict[str, Any] = {
        "from_agent": from_agent,
        "to_agent": to_agent,
        "call_name": call_name,
    }
    if task_id:
        payload["task_id"] = task_id
    if role_preset:
        payload["role_preset"] = role_preset
    if model_tier:
        payload["model_tier"] = model_tier
    if status:
        payload["status"] = status
    if error:
        payload["error"] = error
    if extra:
        payload.update(extra)

    message = f"{from_agent} -> {to_agent} {call_name} ({phase.lower()})"
    _emit_event(
        state=state,
        event_type=f"AGENT_CALL_{phase.upper()}",
        message=message,
        payload=payload,
        node=node,
    )


def _default_budget() -> Dict[str, Any]:
    # 中文注释：默认预算配置
    return {"max_token": 16000, "used_token": 0, "max_retry": 2}


def _estimate_tokens(text: str) -> int:
    # 中文注释：简化 token 估算（按词计数）
    return max(1, len((text or "").split()))


def _normalize_strategy(strategy: str | None) -> str:
    # 中文注释：策略标准化，非法值回退 deep
    normalized = (strategy or "deep").lower()
    allowed = {"quick", "standard", "deep"}
    return normalized if normalized in allowed else "deep"


def determine_model_tier(strategy: str, phase: str) -> str:
    # 中文注释：模型分层策略（small/medium/large 三档）
    normalized = _normalize_strategy(strategy)

    # 中文注释：拆分阶段固定 small，控制成本
    if phase == "decompose":
        return "small"

    # 中文注释：最终综合固定 large，保证质量
    if phase == "finalize":
        return "large"

    # 中文注释：规划阶段：quick/standard/deep 分别对应 small/medium/large
    if normalized == "quick":
        return "small"
    if normalized == "standard":
        return "medium"
    return "large"


def _normalize_task(raw_task: Dict[str, Any], index: int) -> ResearchTask:
    # 中文注释：把 decompose 返回值归一化为内部任务契约
    task_id = str(raw_task.get("id") or f"task-{index}")
    deps_raw = raw_task.get("deps") if isinstance(raw_task.get("deps"), list) else []
    criteria_raw = (
        raw_task.get("acceptance_criteria") if isinstance(raw_task.get("acceptance_criteria"), list) else []
    )
    tools_raw = raw_task.get("tools_allowed") if isinstance(raw_task.get("tools_allowed"), list) else []
    suggested_tools_raw = (
        raw_task.get("suggested_tools") if isinstance(raw_task.get("suggested_tools"), list) else []
    )
    tool_parameters_raw = raw_task.get("tool_parameters") if isinstance(raw_task.get("tool_parameters"), dict) else {}
    output_format_raw = raw_task.get("output_format") if isinstance(raw_task.get("output_format"), dict) else {}
    source_guidance_raw = (
        raw_task.get("source_guidance") if isinstance(raw_task.get("source_guidance"), dict) else {}
    )
    search_budget_raw = raw_task.get("search_budget") if isinstance(raw_task.get("search_budget"), dict) else {}
    boundaries_raw = raw_task.get("boundaries") if isinstance(raw_task.get("boundaries"), dict) else {}

    return {
        "id": task_id,
        "title": str(raw_task.get("title") or f"Task {index}"),
        "goal": str(raw_task.get("goal") or "research"),
        "description": str(raw_task.get("description") or raw_task.get("goal") or "research"),
        "deps": [str(dep) for dep in deps_raw if str(dep).strip()],
        "deliverable": str(raw_task.get("deliverable") or "summary"),
        "acceptance_criteria": [str(c) for c in criteria_raw] or ["produces useful output"],
        "model_tier": str(raw_task.get("model_tier") or "small"),
        "role_preset": str(raw_task.get("role_preset") or "deep_research_agent"),
        "tools_allowed": [str(tool) for tool in tools_raw],
        "estimated_tokens": int(raw_task.get("estimated_tokens") or 500),
        "suggested_tools": [str(tool) for tool in suggested_tools_raw],
        "tool_parameters": {str(k): v for k, v in tool_parameters_raw.items()},
        "output_format": output_format_raw
        or {"type": "narrative", "required_fields": [], "optional_fields": []},
        "source_guidance": source_guidance_raw
        or {"required": ["official", "aggregator"], "optional": ["news"], "avoid": ["social"]},
        "search_budget": search_budget_raw or {"max_queries": 10, "max_fetches": 20},
        "boundaries": boundaries_raw or {"in_scope": [], "out_of_scope": []},
        "parent_area": str(raw_task.get("parent_area")) if raw_task.get("parent_area") is not None else None,
        "status": "pending",
        "retry_count": 0,
    }


def _build_task_graph(tasks: List[Dict[str, Any]]) -> Tuple[Dict[str, ResearchTask], Dict[str, int], Dict[str, List[str]], List[str], List[Dict[str, Any]]]:
    # 中文注释：构建任务图（dependency_count + reverse_dependencies + ready_queue）
    errors: List[Dict[str, Any]] = []
    task_map: Dict[str, ResearchTask] = {}

    for index, raw in enumerate(tasks, start=1):
        if not isinstance(raw, dict):
            errors.append({"type": "invalid_task", "message": f"task[{index}] is not object"})
            continue

        task = _normalize_task(raw, index=index)
        task_id = task["id"]
        if task_id in task_map:
            errors.append({"type": "duplicate_task_id", "message": f"duplicate task id: {task_id}"})
            continue
        task_map[task_id] = task

    dependency_count: Dict[str, int] = {task_id: 0 for task_id in task_map}
    reverse_dependencies: Dict[str, List[str]] = {task_id: [] for task_id in task_map}

    for task_id, task in task_map.items():
        deps = list(task.get("deps") or [])
        valid_deps: List[str] = []
        for dep in deps:
            if dep not in task_map:
                errors.append(
                    {
                        "type": "missing_dependency",
                        "task_id": task_id,
                        "dependency": dep,
                        "message": f"dependency {dep} not found for task {task_id}",
                    }
                )
                continue
            valid_deps.append(dep)
            reverse_dependencies.setdefault(dep, []).append(task_id)
        task["deps"] = valid_deps
        dependency_count[task_id] = len(valid_deps)

    ready_queue = [task_id for task_id, dep_count in dependency_count.items() if dep_count == 0]
    return task_map, dependency_count, reverse_dependencies, ready_queue, errors


def _all_terminal(task_map: Dict[str, ResearchTask]) -> bool:
    # 中文注释：判断所有任务是否进入终态
    terminal = {"succeeded", "failed", "skipped"}
    return all((task.get("status") in terminal) for task in task_map.values())


def _extract_research_areas_for_fallback(state: ResearchState) -> List[str]:
    def _is_meta_instruction(area: str) -> bool:
        lowered = str(area or "").lower()
        markers = [
            "do not output plan",
            "do not output plans",
            "do not output promises",
            "output findings only",
            "prefer parallel decomposition",
            "only synthesis",
            "upstream task",
            "不要输出计划",
            "只输出结论",
            "仅输出结论",
            "上游任务",
        ]
        if any(marker in lowered for marker in markers):
            return True
        return bool(
            re.search(
                r"\bonly\s+synthesis\b.*\bdepend\b|\bdo\s+not\s+output\b.*\bplan|\bprefer\s+parallel\b",
                lowered,
            )
        )

    def _is_transform_instruction(area: str) -> bool:
        lowered = str(area or "").lower()
        transform_markers = [
            "jsonl",
            "question-answer",
            "question answer",
            "q&a",
            "training sample",
            "training data",
            "structured output",
            "结构化",
            "训练数据",
            "问答",
        ]
        action_markers = ["generate", "produce", "output", "format", "生成", "输出"]
        return any(marker in lowered for marker in transform_markers) and any(marker in lowered for marker in action_markers)

    def _is_synthesis_instruction(area: str) -> bool:
        lowered = str(area or "").lower()
        markers = [
            "synthesize",
            "synthesis",
            "cross-check",
            "cross check",
            "compare",
            "difference",
            "improvement",
            "transition",
            "对比",
            "提升",
            "区别",
            "汇总",
            "整合",
            "总结",
        ]
        return any(marker in lowered for marker in markers)

    def _expand_numbered_areas(area_items: List[str]) -> List[str]:
        expanded: List[str] = []
        pattern = re.compile(r"(?:\(\d+\)|（\d+）|\b\d+\))")
        for item in area_items:
            text = _normalize_area_text(item)
            if not text:
                continue
            if not pattern.search(text):
                expanded.append(text)
                continue
            parts = [part.strip(" \t-:;,.") for part in pattern.split(text)]
            for part in parts:
                if not part:
                    continue
                lowered = part.lower()
                if lowered.startswith("independently research these") or lowered.startswith("research these"):
                    continue
                expanded.append(part)
        deduped: List[str] = []
        for item in expanded:
            if item and item not in deduped:
                deduped.append(item)
        return deduped

    def _normalize_area_text(area: str) -> str:
        cleaned = re.sub(r"\s+", " ", str(area or "")).strip(" \t-:|")
        cleaned = cleaned.replace("；", ";").replace("，", ",").replace("：", ":")
        return cleaned

    def _looks_fragmented(area: str) -> bool:
        lowered = area.lower()
        if len(area) < 8:
            return True
        if re.search(r"\barxiv\s*\(line\s*\d{3,5}\)", lowered):
            return True
        if re.fullmatch(r"line\s*\d{3,5}", lowered):
            return True
        if re.fullmatch(r"(?:arxiv|line|\d+|\d+\.\d+|v\d+|paper)\s*", lowered):
            return True
        return False

    def _extract_from_request(user_request: str) -> List[str]:
        text = re.sub(r"\s+", " ", str(user_request or "")).strip()
        if not text:
            return []
        protected_map: Dict[str, str] = {}
        pattern = re.compile(r"\b\d{4}\.\d{4,5}(?:v\d+)?\b", flags=re.IGNORECASE)

        def _protect(match: re.Match[str]) -> str:
            token = f"__ARXIV_ID_{len(protected_map)}__"
            protected_map[token] = match.group(0)
            return token

        normalized = pattern.sub(_protect, text)
        normalized = (
            normalized.replace("；", ";")
            .replace("，", ",")
            .replace("。", ".")
            .replace("、", ",")
            .replace("：", ":")
            .replace("•", ";")
            .replace("\n", ";")
        )
        parts = re.split(
            r"(?:[;!?]|"
            r"\bthen\b|\bnext\b|\bfinally\b|\band then\b|"
            r"然后|接着|最后|并且|并|再|以及)",
            normalized,
            flags=re.IGNORECASE,
        )
        areas: List[str] = []
        for raw in parts:
            area = raw.strip(" \t-:|")
            area = re.sub(r"^(?:and|then|next|finally|并且|然后|接着|最后)\s+", "", area, flags=re.IGNORECASE)
            for token, value in protected_map.items():
                area = area.replace(token, value)
            area = _normalize_area_text(area)
            if _looks_fragmented(area):
                continue
            if _is_meta_instruction(area):
                continue
            if _is_transform_instruction(area):
                continue
            if _is_synthesis_instruction(area):
                continue
            if area not in areas:
                areas.append(area)
            if len(areas) >= 4:
                break
        return _expand_numbered_areas(areas)[:4]

    refined = state.get("refined")
    if isinstance(refined, dict):
        areas = refined.get("research_areas")
        if isinstance(areas, list):
            valid = []
            for item in areas:
                area = _normalize_area_text(str(item))
                if not area or _looks_fragmented(area):
                    continue
                if _is_meta_instruction(area):
                    continue
                if _is_transform_instruction(area):
                    continue
                if _is_synthesis_instruction(area):
                    continue
                valid.append(area)
            valid = _expand_numbered_areas(valid)
            if valid:
                return valid[:4]
    user_request = str(state.get("user_request") or "").strip()
    extracted = _extract_from_request(user_request)
    if extracted:
        return extracted
    return [user_request] if user_request else ["core_problem"]


def _build_fallback_decompose_tasks(state: ResearchState) -> List[Dict[str, Any]]:
    # 中文注释：decompose 超时/失败时的本地兜底拆分（并行优先）
    max_tasks = max(1, min(int(state.get("max_tasks", 6) or 6), 8))
    user_request = str(state.get("user_request") or "")
    areas = _extract_research_areas_for_fallback(state)
    tasks: List[Dict[str, Any]] = []

    query_context = f"{user_request} {' '.join(areas)}".lower()
    wants_comparison = any(
        marker in query_context
        for marker in [
            "compare",
            "vs",
            "difference",
            "improvement",
            "improve",
            "delta",
            "对比",
            "区别",
            "提升",
            "升级",
            "变化",
        ]
    )
    wants_jsonl = any(
        marker in query_context
        for marker in [
            "jsonl",
            "question-answer",
            "question answer",
            "qa ",
            "q&a",
            "training data",
            "structured data",
            "问答",
            "训练数据",
            "结构化",
        ]
    )

    transform_plan: List[str] = []
    if wants_comparison and len(areas) >= 2:
        transform_plan.append("merge")
    if wants_jsonl:
        transform_plan.append("jsonl")

    min_research_needed = 2 if "merge" in transform_plan else 1
    while max_tasks - len(transform_plan) < min_research_needed and transform_plan:
        if "jsonl" in transform_plan:
            transform_plan.remove("jsonl")
        elif "merge" in transform_plan:
            transform_plan.remove("merge")

    research_slots = max(1, max_tasks - len(transform_plan))
    selected_areas = areas[:research_slots]
    if not selected_areas:
        selected_areas = [user_request or "core_problem"]

    for idx, area in enumerate(selected_areas, start=1):
        short_area = re.sub(r"\s+", " ", area).strip()[:100]
        tasks.append(
            {
                "id": f"task-{idx}",
                "title": f"Research {short_area}",
                "goal": f"Collect verifiable evidence about: {area}",
                "description": f"Research key evidence and sources for {area}. Prioritize official and academic references.",
                "deps": [],
                "deliverable": "facts_and_citations",
                "acceptance_criteria": ["contains key findings", "contains source links"],
                "model_tier": "small",
                "role_preset": "deep_research_agent",
                "tools_allowed": ["web_search", "url_select", "web_fetch", "web_crawl", "mcp_fetch"],
                "estimated_tokens": 500,
                "suggested_tools": ["web_search", "url_select", "web_fetch"],
                "tool_parameters": {"query": area},
                "output_format": {"type": "narrative", "required_fields": [], "optional_fields": []},
                "source_guidance": {"required": ["official", "aggregator"], "optional": ["news"], "avoid": ["social"]},
                "search_budget": {"max_queries": 8, "max_fetches": 12},
                "boundaries": {"in_scope": [area], "out_of_scope": []},
                "parent_area": area,
            }
        )

    research_task_ids = [str(task.get("id")) for task in tasks]
    has_merge = False
    if "merge" in transform_plan and len(research_task_ids) >= 2 and len(tasks) < max_tasks:
        tasks.append(
            {
                "id": "task-merge",
                "title": "Cross-check findings",
                "goal": "Cross-check conflicts and unify conclusions across all findings",
                "description": "Resolve conflicts across fetched evidence and produce final synthesis",
                "deps": [str(task.get("id")) for task in tasks],
                "deliverable": "conflict_resolution_note",
                "acceptance_criteria": ["lists conflicts", "provides reconciled conclusion"],
                "model_tier": "small",
                "role_preset": "deep_research_agent",
                "tools_allowed": ["mcp_fetch"],
                "estimated_tokens": 600,
                "suggested_tools": [],
                "tool_parameters": {},
                "output_format": {"type": "narrative", "required_fields": [], "optional_fields": []},
                "source_guidance": {"required": ["official", "aggregator"], "optional": ["news"], "avoid": ["social"]},
                "search_budget": {"max_queries": 0, "max_fetches": 0},
                "boundaries": {"in_scope": ["cross-check"], "out_of_scope": []},
            }
        )
        has_merge = True

    if "jsonl" in transform_plan and len(tasks) < max_tasks:
        jsonl_deps = ["task-merge"] if has_merge else research_task_ids[:]
        tasks.append(
            {
                "id": "task-jsonl",
                "title": "Generate JSONL QA",
                "goal": "Generate structured JSONL question-answer training samples from validated findings",
                "description": "Produce final JSONL output grounded in upstream research evidence and explicitly encode improvements/differences.",
                "deps": jsonl_deps,
                "deliverable": "structured_jsonl",
                "acceptance_criteria": [
                    "outputs valid JSONL lines",
                    "each item is grounded in upstream evidence",
                    "includes comparison/improvement signals when requested",
                ],
                "model_tier": "small",
                "role_preset": "deep_research_agent",
                "tools_allowed": ["mcp_fetch"],
                "estimated_tokens": 700,
                "suggested_tools": [],
                "tool_parameters": {},
                "output_format": {
                    "type": "structured",
                    "required_fields": ["line_id", "question", "answer", "source", "difficulty"],
                    "optional_fields": ["transition", "notes"],
                },
                "source_guidance": {"required": ["official", "aggregator"], "optional": ["news"], "avoid": ["social"]},
                "search_budget": {"max_queries": 0, "max_fetches": 0},
                "boundaries": {"in_scope": ["jsonl generation"], "out_of_scope": ["uncited claims"]},
            }
        )

    return tasks[:max_tasks]


def _compact_refined_for_retry(refined: Dict[str, Any]) -> Dict[str, Any]:
    compact: Dict[str, Any] = {}
    query_type = refined.get("query_type")
    if isinstance(query_type, str) and query_type.strip():
        compact["query_type"] = query_type.strip()

    normalized_question = refined.get("normalized_question")
    if isinstance(normalized_question, str) and normalized_question.strip():
        compact["normalized_question"] = normalized_question.strip()[:400]

    areas = refined.get("research_areas")
    if isinstance(areas, list):
        valid_areas = [str(item).strip()[:120] for item in areas if str(item).strip()]
        if valid_areas:
            compact["research_areas"] = valid_areas[:3]

    complexity = refined.get("complexity")
    if isinstance(complexity, str) and complexity.strip():
        compact["complexity"] = complexity.strip()
    return compact


def _task_text(task: Dict[str, Any]) -> str:
    return (
        f"{task.get('title', '')} {task.get('goal', '')} "
        f"{task.get('description', '')} {task.get('deliverable', '')}"
    ).lower()


def _is_transform_terminal_task(task: Dict[str, Any]) -> bool:
    text = _task_text(task)
    markers = [
        "transform",
        "summarize",
        "summary",
        "synthes",
        "merge",
        "aggregate",
        "jsonl",
        "final",
        "汇总",
        "总结",
        "整合",
        "问答",
    ]
    return any(marker in text for marker in markers)


def _has_transform_terminal_task(task_map: Dict[str, ResearchTask]) -> bool:
    return any(_is_transform_terminal_task(task) for task in task_map.values())


def _downgrade_dependencies_for_parallel(
    task_map: Dict[str, ResearchTask],
) -> Tuple[Dict[str, ResearchTask], Dict[str, int], Dict[str, List[str]], List[str], List[Dict[str, Any]], int]:
    # 中文注释：并行兜底：移除依赖边，尽可能恢复多 root 并发
    raw_tasks: List[Dict[str, Any]] = []
    dropped_edges = 0
    for task in task_map.values():
        item = dict(task)
        deps = [str(dep) for dep in (item.get("deps") or []) if str(dep).strip()]
        dropped_edges += len(deps)
        item["deps"] = []
        raw_tasks.append(item)

    rebuilt_map, dependency_count, reverse_dependencies, ready_queue, rebuild_errors = _build_task_graph(raw_tasks)
    return rebuilt_map, dependency_count, reverse_dependencies, ready_queue, rebuild_errors, dropped_edges


def refine_node(state: ResearchState) -> Dict[str, Any]:
    # 中文注释：调用 LLM Service 进行问题精炼，产出 query_type/research_areas/complexity
    _emit_event(state, "NODE_STARTED", "refine started", payload={}, node="refine")
    try:
        user_request = state.get("user_request", "")
        strategy = _normalize_strategy(state.get("strategy", "deep"))
        llm_service_base_url = state.get("llm_service_base_url", "http://127.0.0.1:8001")

        _emit_agent_call(
            state=state,
            phase="started",
            from_agent="orchestrator.refine_node",
            to_agent="llm_service.refine_agent",
            call_name="/agent/refine",
            node="refine",
            extra={"strategy": strategy},
        )
        client = LLMServiceClient(base_url=llm_service_base_url)
        refined = client.refine(user_request=user_request, strategy=strategy)
        _emit_agent_call(
            state=state,
            phase="completed",
            from_agent="orchestrator.refine_node",
            to_agent="llm_service.refine_agent",
            call_name="/agent/refine",
            node="refine",
            status="ok",
            extra={"query_type": refined.get("query_type")},
        )

        _emit_event(
            state,
            "NODE_COMPLETED",
            "refine completed",
            payload={
                "strategy": strategy,
                "query_type": refined.get("query_type"),
                "research_area_count": len(refined.get("research_areas", []))
                if isinstance(refined.get("research_areas"), list)
                else 0,
            },
            node="refine",
        )

        return {
            "strategy": strategy,
            "planning_tier": determine_model_tier(strategy, phase="planning"),
            "final_tier": determine_model_tier(strategy, phase="finalize"),
            "refined": refined,
            "budget": dict(state.get("budget") or _default_budget()),
            "errors": list(state.get("errors", [])),
        }
    except Exception as exc:  # noqa: BLE001
        _emit_agent_call(
            state=state,
            phase="failed",
            from_agent="orchestrator.refine_node",
            to_agent="llm_service.refine_agent",
            call_name="/agent/refine",
            node="refine",
            status="error",
            error=f"{type(exc).__name__}: {str(exc)}",
        )
        _emit_event(
            state,
            "NODE_FAILED",
            "refine failed",
            payload={"error": f"{type(exc).__name__}: {str(exc)}"},
            node="refine",
        )
        raise


def decompose_node(state: ResearchState) -> Dict[str, Any]:
    # 中文注释：调用 /agent/decompose 拆分子任务（small 模型）
    _emit_event(state, "NODE_STARTED", "decompose started", payload={}, node="decompose")
    try:
        errors = list(state.get("errors", []))
        template_tasks = state.get("template_tasks")
        used_template_tasks = isinstance(template_tasks, list) and bool(template_tasks)
        if isinstance(template_tasks, list) and template_tasks:
            raw_tasks = template_tasks
            _emit_event(
                state,
                "TEMPLATE_TASKS_LOADED",
                "decompose bypassed by workflow template",
                payload={
                    "task_count": len(raw_tasks),
                    "template": state.get("workflow_template_name"),
                },
                node="decompose",
            )
        else:
            llm_service_base_url = state.get("llm_service_base_url", "http://127.0.0.1:8001")
            strategy = _normalize_strategy(state.get("strategy", "deep"))
            user_request = state.get("user_request", "")
            refined = dict(state.get("refined", {}))
            planning_tier = str(state.get("planning_tier") or determine_model_tier(strategy, phase="planning"))

            _emit_agent_call(
                state=state,
                phase="started",
                from_agent="orchestrator.decompose_node",
                to_agent="llm_service.decompose_agent",
                call_name="/agent/decompose",
                node="decompose",
                extra={"strategy": strategy},
            )
            decompose_timeout = max(15.0, min(float(state.get("decompose_timeout_seconds", 120.0) or 120.0), 600.0))
            decompose_http_retries = max(0, min(int(state.get("decompose_http_retries", 1) or 1), 5))
            max_tasks = max(1, min(int(state.get("max_tasks", 6) or 6), 12))
            client = LLMServiceClient(
                base_url=llm_service_base_url,
                timeout=decompose_timeout,
                max_retries=decompose_http_retries,
            )
            try:
                decompose_resp = client.decompose(
                    user_request=user_request,
                    strategy=strategy,
                    refined=refined,
                    max_tasks=max_tasks,
                    role_preset="deep_research_agent",
                    model_tier_hint=planning_tier,
                    timeout=decompose_timeout,
                    max_retries=decompose_http_retries,
                )
                _emit_agent_call(
                    state=state,
                    phase="completed",
                    from_agent="orchestrator.decompose_node",
                    to_agent="llm_service.decompose_agent",
                    call_name="/agent/decompose",
                    node="decompose",
                    status="ok",
                )
                raw_tasks = decompose_resp.get("tasks") if isinstance(decompose_resp.get("tasks"), list) else []
            except Exception as first_exc:  # noqa: BLE001
                _emit_agent_call(
                    state=state,
                    phase="failed",
                    from_agent="orchestrator.decompose_node",
                    to_agent="llm_service.decompose_agent",
                    call_name="/agent/decompose",
                    node="decompose",
                    status="error",
                    error=f"{type(first_exc).__name__}: {str(first_exc)}",
                )
                _emit_event(
                    state,
                    "DECOMPOSE_RETRY_STARTED",
                    "decompose retry with compact context",
                    payload={
                        "reason": f"{type(first_exc).__name__}: {str(first_exc)}",
                        "max_tasks": max(2, min(max_tasks, 4)),
                    },
                    node="decompose",
                )
                compact_refined = _compact_refined_for_retry(refined)
                retry_max_tasks = max(2, min(max_tasks, 4))
                retry_timeout = max(15.0, min(decompose_timeout, 180.0))
                retry_http_retries = max(0, min(decompose_http_retries, 1))
                _emit_agent_call(
                    state=state,
                    phase="started",
                    from_agent="orchestrator.decompose_node",
                    to_agent="llm_service.decompose_agent",
                    call_name="/agent/decompose_retry",
                    node="decompose",
                    extra={"strategy": strategy, "max_tasks": retry_max_tasks},
                )
                try:
                    retry_resp = client.decompose(
                        user_request=user_request,
                        strategy=strategy,
                        refined=compact_refined,
                        max_tasks=retry_max_tasks,
                        role_preset="deep_research_agent",
                        model_tier_hint=planning_tier,
                        timeout=retry_timeout,
                        max_retries=retry_http_retries,
                    )
                    _emit_agent_call(
                        state=state,
                        phase="completed",
                        from_agent="orchestrator.decompose_node",
                        to_agent="llm_service.decompose_agent",
                        call_name="/agent/decompose_retry",
                        node="decompose",
                        status="ok",
                    )
                    raw_tasks = retry_resp.get("tasks") if isinstance(retry_resp.get("tasks"), list) else []
                except Exception as second_exc:  # noqa: BLE001
                    _emit_agent_call(
                        state=state,
                        phase="failed",
                        from_agent="orchestrator.decompose_node",
                        to_agent="llm_service.decompose_agent",
                        call_name="/agent/decompose_retry",
                        node="decompose",
                        status="error",
                        error=f"{type(second_exc).__name__}: {str(second_exc)}",
                    )
                    raw_tasks = _build_fallback_decompose_tasks(state)
                    errors.append(
                        {
                            "type": "decompose_fallback",
                            "message": "llm decompose failed after retry; fallback task plan applied",
                            "reason": f"first={type(first_exc).__name__}: {str(first_exc)}; second={type(second_exc).__name__}: {str(second_exc)}",
                            "task_count": len(raw_tasks),
                        }
                    )
                    _emit_event(
                        state,
                        "DECOMPOSE_FALLBACK",
                        "decompose fallback applied",
                        payload={
                            "task_count": len(raw_tasks),
                            "reason": f"first={type(first_exc).__name__}: {str(first_exc)}; second={type(second_exc).__name__}: {str(second_exc)}",
                        },
                        node="decompose",
                    )

        task_map, dependency_count, reverse_dependencies, ready_queue, build_errors = _build_task_graph(raw_tasks)
        errors = errors + build_errors

        if not task_map:
            errors.append({"type": "decompose_empty", "message": "decompose returned no executable tasks"})
            _emit_event(
                state,
                "NODE_COMPLETED",
                "decompose completed with empty tasks",
                payload={"task_count": 0, "error_count": len(errors)},
                node="decompose",
            )
            return {
                "tasks": [],
                "task_map": {},
                "dependency_count": {},
                "reverse_dependencies": {},
                "ready_queue": [],
                "active_task_ids": [],
                "completed_task_ids": [],
                "task_results": {},
                "errors": errors,
                "done": True,
            }

        # 中文注释：并行保护阈值：任务数较多但首轮只有一个 ready，且无明显终结型任务时触发依赖降级
        if (
            not used_template_tasks
            and len(task_map) >= 3
            and len(ready_queue) == 1
            and not _has_transform_terminal_task(task_map)
        ):
            (
                downgraded_task_map,
                downgraded_dependency_count,
                downgraded_reverse_dependencies,
                downgraded_ready_queue,
                downgrade_errors,
                dropped_edges,
            ) = _downgrade_dependencies_for_parallel(task_map)
            errors.extend(downgrade_errors)
            if dropped_edges > 0:
                task_map = downgraded_task_map
                dependency_count = downgraded_dependency_count
                reverse_dependencies = downgraded_reverse_dependencies
                ready_queue = downgraded_ready_queue
                errors.append(
                    {
                        "type": "dependency_downgrade",
                        "message": "decompose produced overly sequential plan; downgraded dependencies for parallelism",
                        "dropped_edges": dropped_edges,
                        "task_count": len(task_map),
                    }
                )
                _emit_event(
                    state,
                    "DEPENDENCY_DOWNGRADED",
                    "dependency downgrade applied for parallel execution",
                    payload={
                        "dropped_edges": dropped_edges,
                        "ready_count": len(ready_queue),
                    },
                    node="decompose",
                )

        # 中文注释：若所有任务都有依赖且无 ready task，则认为存在环或不可达
        if not ready_queue:
            errors.append({"type": "scheduler_deadlock", "message": "no ready task after decompose"})

        _emit_event(
            state,
            "NODE_COMPLETED",
            "decompose completed",
            payload={
                "task_count": len(task_map),
                "ready_count": len(ready_queue),
                "error_count": len(errors),
            },
            node="decompose",
        )
        return {
            "tasks": list(task_map.values()),
            "task_map": task_map,
            "dependency_count": dependency_count,
            "reverse_dependencies": reverse_dependencies,
            "ready_queue": ready_queue,
            "active_task_ids": [],
            "completed_task_ids": list(state.get("completed_task_ids", [])),
            "task_results": dict(state.get("task_results", {})),
            "errors": errors,
            "done": False,
        }
    except Exception as exc:  # noqa: BLE001
        _emit_agent_call(
            state=state,
            phase="failed",
            from_agent="orchestrator.decompose_node",
            to_agent="llm_service.decompose_agent",
            call_name="/agent/decompose",
            node="decompose",
            status="error",
            error=f"{type(exc).__name__}: {str(exc)}",
        )
        _emit_event(
            state,
            "NODE_FAILED",
            "decompose failed",
            payload={"error": f"{type(exc).__name__}: {str(exc)}"},
            node="decompose",
        )
        raise


def schedule_node(state: ResearchState) -> Dict[str, Any]:
    # 中文注释：从 ready_queue 按并发上限取出一批任务
    ready_queue = list(state.get("ready_queue", []))
    task_map = {task_id: dict(task) for task_id, task in dict(state.get("task_map", {})).items()}

    if not ready_queue:
        _emit_event(
            state,
            "NODE_COMPLETED",
            "schedule idle",
            payload={"active_count": 0, "ready_count": 0},
            node="schedule",
        )
        return {"active_task_ids": [], "task_map": task_map, "ready_queue": ready_queue}

    max_concurrency = int(state.get("max_concurrency", 3) or 3)
    max_concurrency = max(1, min(max_concurrency, 16))

    active_task_ids = ready_queue[:max_concurrency]
    remaining_queue = ready_queue[max_concurrency:]

    for task_id in active_task_ids:
        task = task_map.get(task_id)
        if task:
            task["status"] = "running"

    _emit_event(
        state,
        "TASK_BATCH_SCHEDULED",
        "schedule selected next task batch",
        payload={
            "active_task_ids": active_task_ids,
            "remaining_ready_count": len(remaining_queue),
            "max_concurrency": max_concurrency,
        },
        node="schedule",
    )
    return {
        "active_task_ids": active_task_ids,
        "ready_queue": remaining_queue,
        "task_map": task_map,
    }


def _build_previous_results_for_task(
    state: ResearchState,
    task: Dict[str, Any],
    task_results: Dict[str, Dict[str, Any]],
) -> Dict[str, Any]:
    # 中文注释：共享记忆优先，依赖透传兜底
    deps = [str(dep) for dep in (task.get("deps") or []) if str(dep).strip()]
    run_id = _resolve_thread_id(state)

    shared_payload: Dict[str, Any] = {}
    if run_id and deps:
        for dep in deps:
            records = shared_memory_store.search_records(run_id=run_id, task_id=dep, limit=1)
            if not records:
                continue
            latest = records[0]
            shared_payload[dep] = {
                "status": "ok",
                "content": latest.get("content", ""),
                "citations": [],
                "retrieval_trace": {
                    "policy": "shared_memory",
                    "artifact_path": latest.get("artifact_path"),
                    "stage": latest.get("stage"),
                    "source": "memory_layer",
                },
                "quality_status": "ok",
            }

    if shared_payload:
        _emit_event(
            state,
            "SHARED_MEMORY_HIT",
            "previous_results loaded from shared memory",
            payload={"task_id": str(task.get("id") or ""), "hit_count": len(shared_payload)},
            node="execute",
        )
        return shared_payload

    if deps:
        _emit_event(
            state,
            "SHARED_MEMORY_DEGRADED",
            "shared memory miss, fallback to dependency handoff",
            payload={"task_id": str(task.get("id") or ""), "dependency_count": len(deps)},
            node="execute",
        )

    payload: Dict[str, Any] = {}
    for dep in deps:
        dep_result = task_results.get(dep)
        if not isinstance(dep_result, dict):
            continue
        payload[dep] = {
            "status": dep_result.get("status"),
            "content": dep_result.get("content", ""),
            "citations": dep_result.get("citations", []),
            "retrieval_trace": dep_result.get("retrieval_trace", {}),
            "quality_status": dep_result.get("quality_status"),
        }
    return payload


def _is_low_value_content(text: str) -> bool:
    raw_text = str(text or "")
    lowered = raw_text.lower()
    bad_signals = [
        "no information was retrieved",
        "low relevance summary",
        "sources retrieved do not provide specific guidance",
        "lack of direct access",
        "cannot be completed as specified",
        "no fetched results available",
        "without the actual content from the fetched urls",
        "unable to perform this task",
    ]
    if any(signal in lowered for signal in bad_signals):
        return True

    plan_like_patterns = [
        r"^\s*i(?:\s+will|[' ]?ll)\b",
        r"^\s*i\s+can\s+(?:proceed|continue|fetch|search)\b",
        r"^\s*would\s+you\s+like\s+me\s+to\b",
        r"\bif\s+you\s+want[,]?\s+i\s+can\b",
        r"\bplease\s+confirm\b",
        r"\bnext\s+steps?\b",
        r"如果你愿意",
        r"是否需要我继续",
        r"要不要我继续",
    ]
    return any(re.search(pattern, raw_text, flags=re.IGNORECASE) for pattern in plan_like_patterns)


def _is_effective_result(result: Dict[str, Any]) -> bool:
    if result.get("status") != "ok":
        return False
    if str(result.get("quality_status") or "").lower() in {"insufficient_evidence", "low_relevance"}:
        return False
    if _is_low_value_content(str(result.get("content") or "")):
        return False
    return True


def _execute_single_task(
    base_url: str,
    user_request: str,
    strategy: str,
    refined: Dict[str, Any],
    task: Dict[str, Any],
    previous_results: Dict[str, Any] | None = None,
    strict_output: bool = False,
    quality_mode: str = "best_effort",
) -> Tuple[str, Dict[str, Any]]:
    # 中文注释：执行单个子任务（调用 LLM Service /agent/run）
    task_id = str(task.get("id", ""))
    client = LLMServiceClient(base_url=base_url)
    try:
        result = client.run_task(
            user_request=user_request,
            strategy=strategy,
            refined=refined,
            task=task,
            strict_output=strict_output,
            quality_mode=quality_mode,
            previous_results=previous_results or {},
        )
        status = result.get("status", "error")
        if status != "ok":
            return task_id, {
                "task_id": task_id,
                "status": "error",
                "error": result.get("error") or result.get("content", "agent run failed"),
                "content": result.get("content", ""),
                "model": result.get("model"),
                "model_tier": result.get("model_tier"),
                "role_preset": result.get("role_preset"),
                "tools_allowed": result.get("tools_allowed", []),
                "citations": result.get("citations", []),
                "quality_status": result.get("quality_status"),
                "retrieval_trace": result.get("retrieval_trace", {}),
            }
        return task_id, {
            "task_id": task_id,
            "status": "ok",
            "content": result.get("content", ""),
            "model": result.get("model"),
            "model_tier": result.get("model_tier"),
            "role_preset": result.get("role_preset"),
            "tools_allowed": result.get("tools_allowed", []),
            "citations": result.get("citations", []),
            "retrieval_trace": result.get("retrieval_trace", {}),
            "quality_status": result.get("quality_status"),
        }
    except Exception as exc:  # noqa: BLE001
        return task_id, {
            "task_id": task_id,
            "status": "error",
            "error": f"{type(exc).__name__}: {str(exc)}",
        }


def execute_node(state: ResearchState) -> Dict[str, Any]:
    # 中文注释：并行执行当前批次任务（无依赖任务并发）
    active_task_ids = list(state.get("active_task_ids", []))
    if not active_task_ids:
        _emit_event(
            state,
            "NODE_COMPLETED",
            "execute idle",
            payload={"active_count": 0},
            node="execute",
        )
        return {}

    llm_service_base_url = state.get("llm_service_base_url", "http://127.0.0.1:8001")
    user_request = state.get("user_request", "")
    strategy = _normalize_strategy(state.get("strategy", "deep"))
    refined = dict(state.get("refined", {}))
    strict_output = bool(state.get("strict_output", False))
    quality_mode = str(state.get("quality_mode", "best_effort") or "best_effort")

    task_map = {task_id: dict(task) for task_id, task in dict(state.get("task_map", {})).items()}
    task_results = dict(state.get("task_results", {}))
    budget = dict(state.get("budget") or _default_budget())

    tasks_to_run: List[Dict[str, Any]] = []
    for task_id in active_task_ids:
        task = task_map.get(task_id)
        if task is None:
            task_results[task_id] = {
                "task_id": task_id,
                "status": "error",
                "error": "task not found",
            }
            _emit_event(
                state,
                "TASK_EXECUTION_FAILED",
                "task missing in task_map",
                payload={"task_id": task_id, "error": "task not found"},
                node="execute",
            )
            continue
        tasks_to_run.append(task)

    if tasks_to_run:
        worker_count = min(len(tasks_to_run), max(1, int(state.get("max_concurrency", 3) or 3)))
        for task in tasks_to_run:
            task_id = str(task.get("id") or "")
            role_preset = str(task.get("role_preset") or "deep_research_agent")
            _emit_agent_call(
                state=state,
                phase="started",
                from_agent="orchestrator.execute_node",
                to_agent=f"llm_service.{role_preset}",
                call_name="/agent/run",
                node="execute",
                task_id=task_id,
                role_preset=role_preset,
                model_tier=str(task.get("model_tier") or ""),
            )
        _emit_event(
            state,
            "NODE_STARTED",
            "execute started",
            payload={"task_ids": [str(task.get("id")) for task in tasks_to_run], "worker_count": worker_count},
            node="execute",
        )
        with ThreadPoolExecutor(max_workers=worker_count) as executor:
            futures = {
                executor.submit(
                    _execute_single_task,
                    llm_service_base_url,
                    user_request,
                    strategy,
                    refined,
                    task,
                    _build_previous_results_for_task(state, task, task_results),
                    strict_output,
                    quality_mode,
                ): str(task.get("id"))
                for task in tasks_to_run
            }
            for future in as_completed(futures):
                task_id, result = future.result()
                task_results[task_id] = result
                if result.get("status") == "ok":
                    budget["used_token"] = int(budget.get("used_token", 0)) + _estimate_tokens(
                        str(result.get("content", ""))
                    )
                    role = str(result.get("role_preset") or task_map.get(task_id, {}).get("role_preset") or "deep_research_agent")
                    _emit_agent_call(
                        state=state,
                        phase="completed",
                        from_agent="orchestrator.execute_node",
                        to_agent=f"llm_service.{role}",
                        call_name="/agent/run",
                        node="execute",
                        task_id=task_id,
                        role_preset=role,
                        model_tier=str(result.get("model_tier") or ""),
                        status="ok",
                        extra={"model": result.get("model")},
                    )
                    _emit_event(
                        state,
                        "TASK_EXECUTION_SUCCEEDED",
                        "task executed",
                        payload={
                            "task_id": task_id,
                            "model": result.get("model"),
                            "model_tier": result.get("model_tier"),
                        },
                        node="execute",
                    )
                    try:
                        mem_record = shared_memory_store.upsert_task_record(
                            run_id=_resolve_thread_id(state),
                            task_id=task_id,
                            content=str(result.get("content") or ""),
                            stage=_resolve_phase(state),
                            capability=str(task_map.get(task_id, {}).get("parent_area") or "general"),
                            agent=str(role),
                            artifact_name="final.md",
                            metadata={
                                "model": result.get("model"),
                                "model_tier": result.get("model_tier"),
                            },
                        )
                        quality_raw = result.get("quality_status")
                        quality_score = 1.0 if str(quality_raw or "").lower() == "ok" else 0.7
                        decay_score = 1.0
                        commit_result = git_version_store.commit_task(
                            run_id=_resolve_thread_id(state),
                            task_id=task_id,
                            stage=_resolve_phase(state),
                            files=[
                                str(mem_record.get("artifact_abs_path") or ""),
                                str(mem_record.get("meta_abs_path") or ""),
                                str(mem_record.get("index_abs_path") or ""),
                            ],
                            quality_score=quality_score,
                            decay_score=decay_score,
                            message=f"{str(role)}: append report for {task_id}",
                        )
                        git_version_store.append_log(
                            run_id=_resolve_thread_id(state),
                            payload={
                                "type": "task_commit",
                                "task_id": task_id,
                                "stage": _resolve_phase(state),
                                "result": commit_result,
                            },
                        )
                    except Exception:
                        _emit_event(
                            state,
                            "SHARED_MEMORY_DEGRADED",
                            "failed to persist task result to shared memory or version layer",
                            payload={"task_id": task_id},
                            node="execute",
                        )
                else:
                    role = str(result.get("role_preset") or task_map.get(task_id, {}).get("role_preset") or "deep_research_agent")
                    _emit_agent_call(
                        state=state,
                        phase="failed",
                        from_agent="orchestrator.execute_node",
                        to_agent=f"llm_service.{role}",
                        call_name="/agent/run",
                        node="execute",
                        task_id=task_id,
                        role_preset=role,
                        model_tier=str(result.get("model_tier") or ""),
                        status="error",
                        error=str(result.get("error") or "unknown error"),
                    )
                    _emit_event(
                        state,
                        "TASK_EXECUTION_FAILED",
                        "task execution failed",
                        payload={"task_id": task_id, "error": result.get("error")},
                        node="execute",
                    )

        _emit_event(
            state,
            "NODE_COMPLETED",
            "execute completed",
            payload={"task_result_count": len(task_results), "used_token": int(budget.get("used_token", 0))},
            node="execute",
        )

    return {
        "task_results": task_results,
        "budget": budget,
    }


def verify_merge_node(state: ResearchState) -> Dict[str, Any]:
    # 中文注释：执行后更新任务状态、解锁依赖任务、处理失败重试与终止条件
    _emit_event(state, "NODE_STARTED", "verify started", payload={}, node="verify")
    active_task_ids = list(state.get("active_task_ids", []))
    task_results = dict(state.get("task_results", {}))
    task_map = {task_id: dict(task) for task_id, task in dict(state.get("task_map", {})).items()}
    dependency_count = dict(state.get("dependency_count", {}))
    reverse_dependencies = {
        task_id: list(task_ids) for task_id, task_ids in dict(state.get("reverse_dependencies", {})).items()
    }
    ready_queue = list(state.get("ready_queue", []))
    errors = list(state.get("errors", []))
    completed_task_ids = set(state.get("completed_task_ids", []))

    max_retry = int(dict(state.get("budget") or _default_budget()).get("max_retry", 2))
    succeeded: List[str] = []
    failed: List[str] = []

    for task_id in active_task_ids:
        task = task_map.get(task_id)
        if task is None:
            errors.append({"type": "missing_task_state", "task_id": task_id, "message": "task missing in task_map"})
            continue

        result = task_results.get(task_id, {})
        if _is_effective_result(result):
            task["status"] = "succeeded"
            completed_task_ids.add(task_id)
            succeeded.append(task_id)
            continue

        retry_count = int(task.get("retry_count", 0)) + 1
        task["retry_count"] = retry_count
        if retry_count <= max_retry:
            task["status"] = "pending"
            if task_id not in ready_queue:
                ready_queue.append(task_id)
            errors.append(
                {
                    "type": "task_retry",
                    "task_id": task_id,
                    "retry_count": retry_count,
                    "message": f"task retry scheduled ({retry_count}/{max_retry})",
                    "reason": result.get("error") or result.get("quality_status") or "non-effective result",
                }
            )
        else:
            task["status"] = "failed"
            failed.append(task_id)
            errors.append(
                {
                    "type": "task_failed",
                    "task_id": task_id,
                    "retry_count": retry_count,
                    "message": "task failed after retry limit",
                }
            )

    # 中文注释：成功任务会减少后继任务的依赖计数，归零后入 ready_queue
    for task_id in succeeded:
        for dependent_id in reverse_dependencies.get(task_id, []):
            dependent_task = task_map.get(dependent_id)
            if dependent_task is None:
                continue
            if dependent_task.get("status") != "pending":
                continue

            remaining = max(0, int(dependency_count.get(dependent_id, 0)) - 1)
            dependency_count[dependent_id] = remaining
            if remaining == 0 and dependent_id not in ready_queue:
                ready_queue.append(dependent_id)
                _emit_event(
                    state,
                    "AGENT_HANDOFF",
                    "dependency resolved and task activated",
                    payload={
                        "from_task_id": task_id,
                        "to_task_id": dependent_id,
                        "reason": "dependencies satisfied",
                    },
                    node="verify",
                )

    # 中文注释：失败任务会级联阻断依赖它的后继任务
    blocked_queue = list(failed)
    while blocked_queue:
        source_id = blocked_queue.pop(0)
        for dependent_id in reverse_dependencies.get(source_id, []):
            dependent_task = task_map.get(dependent_id)
            if dependent_task is None:
                continue
            if dependent_task.get("status") in {"succeeded", "failed", "skipped"}:
                continue
            dependent_task["status"] = "skipped"
            if dependent_id in ready_queue:
                ready_queue.remove(dependent_id)
            errors.append(
                {
                    "type": "task_skipped",
                    "task_id": dependent_id,
                    "message": f"skipped because dependency {source_id} failed",
                }
            )
            _emit_event(
                state,
                "AGENT_BLOCKED",
                "task blocked by failed dependency",
                payload={
                    "from_task_id": source_id,
                    "to_task_id": dependent_id,
                    "reason": "dependency failed",
                },
                node="verify",
            )
            blocked_queue.append(dependent_id)

    done = False
    if _all_terminal(task_map):
        done = True
    elif ready_queue:
        done = False
    else:
        # 中文注释：无活跃任务且无可调度任务，但仍有未终态任务，判定为死锁并终止
        non_terminal = [task_id for task_id, task in task_map.items() if task.get("status") not in {"succeeded", "failed", "skipped"}]
        if non_terminal:
            for task_id in non_terminal:
                task_map[task_id]["status"] = "skipped"
            errors.append(
                {
                    "type": "scheduler_deadlock",
                    "message": "no ready task and non-terminal tasks remain",
                    "task_ids": non_terminal,
                }
            )
            done = True

    skipped_count = sum(1 for task in task_map.values() if task.get("status") == "skipped")
    _emit_event(
        state,
        "NODE_COMPLETED",
        "verify completed",
        payload={
            "succeeded_count": len(succeeded),
            "failed_count": len(failed),
            "skipped_count": skipped_count,
            "ready_count": len(ready_queue),
            "done": done,
        },
        node="verify",
    )

    return {
        "task_map": task_map,
        "tasks": list(task_map.values()),
        "dependency_count": dependency_count,
        "reverse_dependencies": reverse_dependencies,
        "ready_queue": ready_queue,
        "completed_task_ids": sorted(completed_task_ids),
        "errors": errors,
        "active_task_ids": [],
        "done": done,
    }


def finalize_node(state: ResearchState) -> Dict[str, Any]:
    # 中文注释：汇总子任务结果并调用大模型生成最终答案
    _emit_event(state, "NODE_STARTED", "finalize started", payload={}, node="finalize")
    task_map = dict(state.get("task_map", {}))
    task_results = dict(state.get("task_results", {}))
    llm_service_base_url = state.get("llm_service_base_url", "http://127.0.0.1:8001")

    completed_payload: List[Dict[str, Any]] = []
    for task_id, task in task_map.items():
        if task.get("status") != "succeeded":
            continue
        result = task_results.get(task_id)
        if not result:
            continue
        completed_payload.append(
            {
                "task_id": task_id,
                "title": task.get("title"),
                "goal": task.get("goal"),
                "content": result.get("content", ""),
            }
        )

    summary_prompt = (
        "You are a research synthesizer. Merge all task outputs into a final answer.\n"
        f"User request: {state.get('user_request', '')}\n"
        f"Refined context: {json.dumps(state.get('refined', {}), ensure_ascii=False)}\n"
        f"Task results: {json.dumps(completed_payload, ensure_ascii=False)}"
    )

    summary_content = ""
    final_errors = list(state.get("errors", []))
    try:
        _emit_agent_call(
            state=state,
            phase="started",
            from_agent="orchestrator.finalize_node",
            to_agent="llm_service.finalizer",
            call_name="/v1/responses",
            node="finalize",
            model_tier=str(state.get("final_tier", "large")),
        )
        client = LLMServiceClient(base_url=llm_service_base_url)
        response = client.respond(
            prompt=summary_prompt,
            model_tier=str(state.get("final_tier", "large")),
            system_prompt="You are a strict synthesis reviewer. Keep the answer factual and structured.",
        )
        summary_content = str(response.get("content", ""))
        _emit_agent_call(
            state=state,
            phase="completed",
            from_agent="orchestrator.finalize_node",
            to_agent="llm_service.finalizer",
            call_name="/v1/responses",
            node="finalize",
            model_tier=str(state.get("final_tier", "large")),
            status="ok",
            extra={"model": response.get("model")},
        )
    except Exception as exc:  # noqa: BLE001
        _emit_agent_call(
            state=state,
            phase="failed",
            from_agent="orchestrator.finalize_node",
            to_agent="llm_service.finalizer",
            call_name="/v1/responses",
            node="finalize",
            model_tier=str(state.get("final_tier", "large")),
            status="error",
            error=f"{type(exc).__name__}: {str(exc)}",
        )
        summary_content = f"[finalize-fallback] {type(exc).__name__}: {str(exc)}"
        final_errors.append(
            {
                "type": "finalize_failed",
                "message": "final summary generation failed",
                "error": f"{type(exc).__name__}: {str(exc)}",
            }
        )

    final_output = {
        "request": state.get("user_request"),
        "strategy": state.get("strategy"),
        "refined": state.get("refined", {}),
        "completed_task_count": len(completed_payload),
        "task_results": completed_payload,
        "summary": summary_content,
        "errors": final_errors,
        "budget": state.get("budget", _default_budget()),
    }
    _emit_event(
        state,
        "NODE_COMPLETED",
        "finalize completed",
        payload={
            "completed_task_count": len(completed_payload),
            "summary_preview": str(summary_content)[:120],
        },
        node="finalize",
    )
    return {"done": True, "final_output": final_output, "errors": final_errors}


def route_after_schedule(state: ResearchState) -> str:
    # 中文注释：调度后有任务就执行，没有则进入 verify 做终态判定
    return "execute" if state.get("active_task_ids") else "verify"


def route_after_verify(state: ResearchState) -> str:
    # 中文注释：流程完成则 finalize，否则继续调度下一批任务
    if state.get("done"):
        return "finalize"
    return "schedule"


def build_graph(checkpointer):
    # 中文注释：构建 LangGraph 并绑定 checkpointer
    graph = StateGraph(ResearchState)

    graph.add_node("refine", refine_node)
    graph.add_node("decompose", decompose_node)
    graph.add_node("schedule", schedule_node)
    graph.add_node("execute", execute_node)
    graph.add_node("verify", verify_merge_node)
    graph.add_node("finalize", finalize_node)

    graph.add_edge(START, "refine")
    graph.add_edge("refine", "decompose")
    graph.add_edge("decompose", "schedule")

    graph.add_conditional_edges(
        "schedule",
        route_after_schedule,
        {
            "execute": "execute",
            "verify": "verify",
        },
    )

    graph.add_edge("execute", "verify")
    graph.add_conditional_edges(
        "verify",
        route_after_verify,
        {
            "schedule": "schedule",
            "finalize": "finalize",
        },
    )

    graph.add_edge("finalize", END)
    return graph.compile(checkpointer=checkpointer)


def list_checkpoints(app, thread_id: str, limit: int = 20) -> List[Dict[str, Any]]:
    # 中文注释：列出某线程的 checkpoint 历史
    config = {"configurable": {"thread_id": thread_id}}
    snapshots = list(app.get_state_history(config, limit=limit))
    return [
        {
            "checkpoint_id": snapshot.config.get("configurable", {}).get("checkpoint_id"),
            "created_at": snapshot.created_at,
            "values": snapshot.values,
        }
        for snapshot in snapshots
    ]


def restore_checkpoint(app, thread_id: str, checkpoint_id: str) -> Dict[str, Any]:
    # 中文注释：读取指定 checkpoint 的状态并写回当前线程状态（time travel）
    config = {"configurable": {"thread_id": thread_id, "checkpoint_id": checkpoint_id}}
    snapshot = app.get_state(config)
    app.update_state({"configurable": {"thread_id": thread_id}}, snapshot.values)
    return snapshot.values
