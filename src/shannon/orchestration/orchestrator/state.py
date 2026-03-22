from __future__ import annotations

from typing import Any, Dict, List, Optional, TypedDict

# 中文注释：编排层状态定义（LangGraph 全局状态）


class ResearchTask(TypedDict, total=False):
    # 中文注释：任务基础字段（契约）
    id: str
    title: str
    goal: str
    description: str
    deps: List[str]
    deliverable: str
    acceptance_criteria: List[str]

    # 中文注释：执行控制字段
    model_tier: str
    role_preset: str
    tools_allowed: List[str]
    estimated_tokens: int
    suggested_tools: List[str]
    tool_parameters: Dict[str, Any]
    output_format: Dict[str, Any]
    source_guidance: Dict[str, Any]
    search_budget: Dict[str, Any]
    boundaries: Dict[str, Any]
    parent_area: Optional[str]
    status: str  # pending/running/succeeded/failed/skipped
    retry_count: int


class ResearchState(TypedDict, total=False):
    # 中文注释：输入参数
    user_request: str
    strategy: str  # unified deep semantics; legacy quick/standard map to deep
    thread_id: str
    max_concurrency: int
    max_tasks: int
    llm_service_base_url: str
    workflow_template_name: str
    workflow_template_path: str
    workflow_context: Dict[str, Any]
    template_tasks: List[ResearchTask]

    # 中文注释：模型分层与问题精炼上下文
    planning_tier: str
    final_tier: str
    refined: Dict[str, Any]  # query_type/research_areas/complexity/normalized_question

    # 中文注释：拆分任务与拓扑调度结构
    tasks: List[ResearchTask]
    task_map: Dict[str, ResearchTask]
    dependency_count: Dict[str, int]
    reverse_dependencies: Dict[str, List[str]]
    ready_queue: List[str]
    active_task_ids: List[str]
    completed_task_ids: List[str]

    # 中文注释：执行结果与异常
    task_results: Dict[str, Dict[str, Any]]
    errors: List[Dict[str, Any]]

    # 中文注释：质量控制参数
    strict_output: bool  # True 时禁用转换任务的确定性 fallback 短路
    quality_mode: str  # "strict" | "best_effort"

    # 中文注释：预算与流程控制
    budget: Dict[str, Any]  # max_token/used_token/max_retry
    done: bool

    # 中文注释：最终输出
    final_output: Optional[Dict[str, Any]]
