from __future__ import annotations

import json
import os
import re
from typing import Any, Dict, List, Optional
from urllib.parse import urlparse

from fastapi import FastAPI
from pydantic import BaseModel, ConfigDict, Field

from shannon.llm_service.client.openai_client import OpenAIClient
from shannon.llm_service.presets import get_preset
from shannon.llm_service.prompt_expert import build_prompt_contract
from shannon.llm_service.prompts import (
    INTERPRETATION_PROMPT_GENERAL,
    INTERPRETATION_PROMPT_SOURCES,
    PROMPT_VERSION,
    RESEARCH_MODE_INSTRUCTION,
    build_decompose_system_prompt,
    should_use_source_format,
)
from shannon.llm_service.provider_manager import ModelTier, resolve_model
from shannon.llm_service.retrieval.crawler import web_crawl
from shannon.llm_service.retrieval.fetcher import web_fetch
from shannon.llm_service.retrieval.pipeline import run_search_first_pipeline
from shannon.llm_service.retrieval.search import web_search
from shannon.llm_service.retrieval.selector import select_candidate_urls
from shannon.llm_service.tool_calling.executor import execute_tool_call
from shannon.utils.env import load_env

# 中文注释：在初始化向量存储前加载 .env，避免本地运行时误降级到内存
load_env()

from shannon.storage.qdrant.vector_store import vector_store

# 中文注释：LLM Service 入口
app = FastAPI(title="Shannon LLM Service", version="0.3.0")


# 中文注释：统一请求/响应模型基类，允许 model_tier 这类字段名
class ShannonBaseModel(BaseModel):
    model_config = ConfigDict(protected_namespaces=())


# 中文注释：类 CompletionRequest 的入口（兼容旧接口）
class CompletionRequest(ShannonBaseModel):
    prompt: str
    model: str = "gpt-4o-mini"
    temperature: float = 0.3


# 中文注释：类 CompletionResponse 的入口
class CompletionResponse(ShannonBaseModel):
    content: str


# 中文注释：类 ResponsesRequest 的入口
class ResponsesRequest(ShannonBaseModel):
    prompt: str
    model_tier: str = ModelTier.SMALL.value
    model: Optional[str] = None
    temperature: float = 0.3
    system_prompt: Optional[str] = None


# 中文注释：类 ResponsesResponse 的入口
class ResponsesResponse(ShannonBaseModel):
    content: str
    model: str
    model_tier: str


# 中文注释：类 ToolCallRequest 的入口
class ToolCallRequest(ShannonBaseModel):
    name: str
    arguments: dict


# 中文注释：类 RefineRequest 的入口
class RefineRequest(ShannonBaseModel):
    user_request: str
    strategy: str = "deep"


# 中文注释：类 RefineResponse 的入口
class RefineResponse(ShannonBaseModel):
    query_type: str
    research_areas: List[str]
    complexity: str
    normalized_question: str


# 中文注释：类 TaskContract 的入口
class TaskContract(ShannonBaseModel):
    id: str
    title: str
    goal: str
    description: str = ""
    deps: List[str] = Field(default_factory=list)
    deliverable: str
    acceptance_criteria: List[str] = Field(default_factory=list)
    model_tier: str = ModelTier.SMALL.value
    role_preset: str = "deep_research_agent"
    tools_allowed: List[str] = Field(default_factory=list)
    estimated_tokens: int = 500
    suggested_tools: List[str] = Field(default_factory=list)
    tool_parameters: Dict[str, Any] = Field(default_factory=dict)
    output_format: Dict[str, Any] = Field(default_factory=dict)
    source_guidance: Dict[str, Any] = Field(default_factory=dict)
    search_budget: Dict[str, Any] = Field(default_factory=dict)
    boundaries: Dict[str, Any] = Field(default_factory=dict)
    parent_area: Optional[str] = None


# 中文注释：类 DecomposeRequest 的入口
class DecomposeRequest(ShannonBaseModel):
    user_request: str
    strategy: str = "deep"
    refined: Dict[str, Any] = Field(default_factory=dict)
    max_tasks: int = 6
    role_preset: str = "deep_research_agent"
    model_tier_hint: Optional[str] = None


# 中文注释：类 DecomposeResponse 的入口
class DecomposeResponse(ShannonBaseModel):
    prompt_version: str
    model: str
    model_tier: str
    tasks: List[TaskContract]


# 中文注释：类 AgentRunRequest 的入口
class AgentRunRequest(ShannonBaseModel):
    user_request: str
    strategy: str = "deep"
    refined: Dict[str, Any] = Field(default_factory=dict)
    task: TaskContract
    previous_results: Dict[str, Any] = Field(default_factory=dict)
    max_search_rounds: int = 2
    per_round_fetch_limit: int = 3
    # 中文注释：strict_output=true 时，转换任务不走确定性短路 fallback，强制调用 LLM
    strict_output: bool = False
    # 中文注释：quality_mode 控制低价值输出的处理策略
    #   "best_effort" (默认)：允许 fallback 但写入 degraded 标记
    #   "strict"：保持 error 状态，让编排层触发重试
    quality_mode: str = "best_effort"


# 中文注释：类 AgentRunResponse 的入口
class AgentRunResponse(ShannonBaseModel):
    task_id: str
    status: str
    content: str
    error: str = ""
    model: str
    model_tier: str
    role_preset: str
    tools_allowed: List[str] = Field(default_factory=list)
    citations: List[Dict[str, Any]] = Field(default_factory=list)
    retrieval_trace: Dict[str, Any] = Field(default_factory=dict)
    quality_status: str = "unknown"


# 中文注释：类 WebSearchRequest 的入口
class WebSearchRequest(ShannonBaseModel):
    query: str
    max_results: int = 8
    domains: List[str] = Field(default_factory=list)


# 中文注释：类 URLSelectRequest 的入口
class URLSelectRequest(ShannonBaseModel):
    query: str
    candidates: List[Dict[str, Any]] = Field(default_factory=list)
    max_urls: int = 3


# 中文注释：类 WebFetchRequest 的入口
class WebFetchRequest(ShannonBaseModel):
    urls: List[str] = Field(default_factory=list)
    max_chars: int = 12000


# 中文注释：类 WebCrawlRequest 的入口
class WebCrawlRequest(ShannonBaseModel):
    seed_urls: List[str] = Field(default_factory=list)
    max_pages_per_seed: int = 2
    max_total_pages: int = 6
    max_chars: int = 10000


# 中文注释：类 MemoryUpsertRequest 的入口
class MemoryUpsertRequest(ShannonBaseModel):
    text: str
    payload: Dict[str, Any] = Field(default_factory=dict)
    collection: str = "task_memories"


# 中文注释：类 MemorySearchRequest 的入口
class MemorySearchRequest(ShannonBaseModel):
    query: str
    limit: int = 5
    collection: str = "task_memories"
    filter_payload: Dict[str, Any] = Field(default_factory=dict)


# 中文注释：类 PromptExpertRequest 的入口
class PromptExpertRequest(ShannonBaseModel):
    role_preset: str = "deep_research_agent"
    task: Dict[str, Any] = Field(default_factory=dict)
    user_request: str = ""
    refined: Dict[str, Any] = Field(default_factory=dict)


# 中文注释：类 PromptExpertResponse 的入口
class PromptExpertResponse(ShannonBaseModel):
    contract_version: str
    role_preset: str
    role_prompt: str
    task_prompt: str
    constraints: List[str] = Field(default_factory=list)
    source: str = "prompt_expert"


_META_INSTRUCTION_MARKERS = [
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
    "仅允许",
    "上游任务",
]


def _is_meta_instruction_text(value: str) -> bool:
    lowered = str(value or "").lower()
    if any(marker in lowered for marker in _META_INSTRUCTION_MARKERS):
        return True
    return bool(
        re.search(
            r"\bonly\s+synthesis\b.*\bdepend\b|\bdo\s+not\s+output\b.*\bplan|\bprefer\s+parallel\b",
            lowered,
        )
    )


def _is_transform_instruction_text(value: str) -> bool:
    lowered = str(value or "").lower()
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


def _is_synthesis_instruction_text(value: str) -> bool:
    lowered = str(value or "").lower()
    markers = [
        "synthesize",
        "synthesis",
        "cross-check",
        "cross check",
        "compare",
        "difference",
        "improvement",
        "benchmark methodology",
        "transition",
        "对比",
        "提升",
        "区别",
        "汇总",
        "整合",
        "总结",
    ]
    return any(marker in lowered for marker in markers)


def _expand_numbered_research_areas(areas: List[str]) -> List[str]:
    expanded: List[str] = []
    pattern = re.compile(r"(?:\(\d+\)|（\d+）|\b\d+\))")
    for area in areas:
        text = re.sub(r"\s+", " ", str(area or "")).strip()
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
    for area in expanded:
        if area and area not in deduped:
            deduped.append(area)
    return deduped


# 中文注释：函数 _extract_areas 的入口
def _extract_areas(user_request: str) -> List[str]:
    # 中文注释：按语义片段抽取主题，避免退化为单词级拆分
    text = re.sub(r"\s+", " ", (user_request or "")).strip()
    if not text:
        return ["core_problem"]

    protected_text = text
    protected_map: Dict[str, str] = {}
    arxiv_pattern = re.compile(r"\b\d{4}\.\d{4,5}(?:v\d+)?\b", flags=re.IGNORECASE)

    def _protect_arxiv(match: re.Match[str]) -> str:
        token = f"__ARXIV_ID_{len(protected_map)}__"
        protected_map[token] = match.group(0)
        return token

    protected_text = arxiv_pattern.sub(_protect_arxiv, protected_text)
    normalized = (
        protected_text.replace("；", ";")
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
        r"然后|接着|最后|并且|并|再|以及|并且)",
        normalized,
        flags=re.IGNORECASE,
    )

    areas: List[str] = []
    for raw in parts:
        area = raw.strip(" \t-:|")
        area = re.sub(r"^(?:and|then|next|finally|并且|然后|接着|最后)\s+", "", area, flags=re.IGNORECASE)
        for token, value in protected_map.items():
            area = area.replace(token, value)
        if len(area) < 8:
            continue
        if _is_meta_instruction_text(area):
            continue
        if _is_transform_instruction_text(area):
            continue
        if area not in areas:
            areas.append(area)
        if len(areas) >= 4:
            break
    return _expand_numbered_research_areas(areas)[:4] or ["core_problem"]


def _is_model_error_content(content: str) -> bool:
    # 中文注释：识别模型调用降级错误文本，避免误判执行成功
    stripped = (content or "").strip()
    return bool(re.match(r"^\[(error|fallback):", stripped, flags=re.IGNORECASE))


def _extract_query_terms(text: str, max_terms: int = 8) -> List[str]:
    parts = re.split(r"[^0-9A-Za-z\u4e00-\u9fff]+", (text or "").lower())
    terms: List[str] = []
    stopwords = {
        "the",
        "and",
        "or",
        "for",
        "with",
        "from",
        "that",
        "this",
        "using",
        "then",
        "top",
        "paper",
        "papers",
    }
    for token in parts:
        clean = token.strip()
        if len(clean) < 3 or clean in stopwords:
            continue
        if clean not in terms:
            terms.append(clean)
        if len(terms) >= max_terms:
            break
    return terms


def _is_transform_only_task(task: TaskContract) -> bool:
    """判定任务是否为纯格式转换/汇总类任务（不需要新检索）。

    收窄匹配条件：仅保留强信号（structured_jsonl deliverable、明确 required_fields、
    reformat/convert 等关键词），移除泛词 "generate" 以避免误判需要 LLM
    实质生成的任务。
    """
    text = f"{task.title} {task.goal} {task.description}".lower()
    output_type = str(task.output_format.get("type") or "").lower() if isinstance(task.output_format, dict) else ""
    required_fields = (
        {str(item).lower() for item in (task.output_format.get("required_fields") or [])}
        if isinstance(task.output_format, dict) and isinstance(task.output_format.get("required_fields"), list)
        else set()
    )
    deliverable = str(task.deliverable or "").lower()

    # 中文注释：结构化 QA/JSONL 任务 —— 仅当 deliverable 明确为 structured_jsonl
    # 或 required_fields 完整匹配 QA 三元组时才视为转换任务
    if "structured_jsonl" in deliverable:
        return True
    if {"line_id", "question", "answer"} <= required_fields:
        return True

    # 中文注释：强信号关键词匹配（去掉了泛词 generate / format / summarize，保留 jsonl）
    transform_markers = [
        "jsonl",
        "reformat",
        "convert format",
        "sort",
        "select the top",
        "extract the abstract",
        "training sample",
    ]
    research_markers = [
        "research",
        "search",
        "collect evidence",
        "find source",
        "verify",
        "fetch",
    ]
    has_transform = any(marker in text for marker in transform_markers)
    has_research = any(marker in text for marker in research_markers)
    return has_transform and not has_research


_RETRIEVAL_TOOLS = {"web_search", "tavily_search", "url_select", "web_fetch", "web_crawl", "mcp_fetch"}


def _task_text(task: TaskContract) -> str:
    return f"{task.title} {task.goal} {task.description}".lower()


def _is_synthesis_task(task: TaskContract) -> bool:
    text = _task_text(task)
    markers = [
        "synthes",
        "merge",
        "cross-check",
        "cross check",
        "summary",
        "summarize",
        "conclusion",
        "jsonl",
        "aggregate",
        "final answer",
        "汇总",
        "总结",
        "整合",
        "问答",
    ]
    return any(marker in text for marker in markers)


def _is_retrieval_task(task: TaskContract) -> bool:
    tools = {str(tool).lower() for tool in (task.tools_allowed + task.suggested_tools)}
    if tools & _RETRIEVAL_TOOLS:
        return True
    text = _task_text(task)
    markers = ["research", "search", "fetch", "crawl", "evidence", "source", "检索", "抓取", "搜索"]
    return any(marker in text for marker in markers)


def _converge_task_dependencies(tasks: List[TaskContract], max_layers: int = 2) -> List[TaskContract]:
    # 中文注释：依赖收敛器：默认并行，仅允许转换/汇总类任务依赖上游，并限制图深度
    if not tasks:
        return tasks

    valid_ids = {str(task.id) for task in tasks if str(task.id).strip()}
    allow_dependency: Dict[str, bool] = {}
    source_ids: List[str] = []
    synthesis_ids: List[str] = []

    for task in tasks:
        task_id = str(task.id)
        is_transform = _is_transform_only_task(task)
        is_synthesis = _is_synthesis_task(task)
        allow = is_transform or is_synthesis
        allow_dependency[task_id] = allow

        # 中文注释：检索类且非转换/汇总任务强制并行（deps = []）
        if _is_retrieval_task(task) and not allow:
            source_ids.append(task_id)
        elif not allow:
            source_ids.append(task_id)
        if is_synthesis and not is_transform:
            synthesis_ids.append(task_id)

    source_ids = list(dict.fromkeys([task_id for task_id in source_ids if task_id in valid_ids]))
    synthesis_ids = list(dict.fromkeys([task_id for task_id in synthesis_ids if task_id in valid_ids]))

    # 中文注释：第一轮清洗：仅保留合法依赖，且非转换/汇总任务去依赖
    for task in tasks:
        task_id = str(task.id)
        deps = [
            str(dep)
            for dep in (task.deps or [])
            if str(dep).strip() and str(dep) in valid_ids and str(dep) != task_id
        ]
        if not allow_dependency.get(task_id, False):
            task.deps = []
            continue
        task.deps = list(dict.fromkeys(deps))

    # 中文注释：第二轮限制深度：最多两层（采集层 + 汇总层），即依赖只能指向根层任务
    # 特例：转换任务允许依赖浅层汇总任务（仅依赖根层的汇总任务），形成
    # research → synthesis → transform 的标准三层流水线
    if max_layers <= 2:
        root_ids = [str(task.id) for task in tasks if not task.deps]
        root_set = set(root_ids)
        synthesis_set = set(synthesis_ids)
        task_by_id = {str(t.id): t for t in tasks}
        shallow_synthesis: set = set()
        for tid in synthesis_set:
            t = task_by_id.get(tid)
            if t is not None and all(dep in root_set for dep in (t.deps or [])):
                shallow_synthesis.add(tid)
        for task in tasks:
            if not task.deps:
                continue
            # 中文注释：JSONL/结构化转换任务允许依赖浅层汇总任务 + 根层任务
            if _is_transform_only_task(task):
                allowed = root_set | shallow_synthesis
                task.deps = list(dict.fromkeys([dep for dep in task.deps if dep in allowed]))
            else:
                task.deps = list(dict.fromkeys([dep for dep in task.deps if dep in root_set]))

    # 中文注释：转换/汇总任务若无依赖，自动依赖采集层，避免无上游输入导致空转
    # 仅挂接根层任务，防止重新引入超 2 层链
    root_set_post = {str(task.id) for task in tasks if not task.deps}
    for task in tasks:
        task_id = str(task.id)
        if not allow_dependency.get(task_id, False):
            continue
        if task.deps:
            continue
        # 中文注释：优先选择根层的汇总任务，其次选择采集层根任务
        preferred_roots = [dep for dep in synthesis_ids if dep != task_id and dep in root_set_post]
        fallback_roots = [dep for dep in source_ids if dep != task_id and dep in root_set_post]
        if _is_transform_only_task(task) or _is_synthesis_task(task):
            task.deps = preferred_roots or fallback_roots

    for task in tasks:
        task_id = str(task.id)
        task.deps = list(
            dict.fromkeys(
                [str(dep) for dep in (task.deps or []) if str(dep).strip() and str(dep) in valid_ids and str(dep) != task_id]
            )
        )

    return tasks


def _infer_retrieval_domains(user_request: str, task: TaskContract) -> List[str]:
    text = f"{user_request} {task.goal} {task.description}"
    domains: List[str] = []

    # 中文注释：支持 site:domain 语法
    for item in re.findall(r"\bsite:([A-Za-z0-9.-]+\.[A-Za-z]{2,})\b", text, flags=re.IGNORECASE):
        domains.append(item.lower())

    # 中文注释：从显式 URL 中提取域名
    for url in re.findall(r"https?://[^\s)>\"]+", text, flags=re.IGNORECASE):
        try:
            host = (urlparse(url).netloc or "").lower()
        except Exception:  # noqa: BLE001
            host = ""
        if host:
            domains.append(host)

    # 中文注释：从裸域名 token 中提取（例如 docs.example.com）
    for token in re.findall(r"\b(?:[A-Za-z0-9-]+\.)+[A-Za-z]{2,}\b", text):
        if "." in token:
            domains.append(token.lower())

    # 去重并过滤无效域名
    normalized: List[str] = []
    for domain in domains:
        cleaned = domain.strip().strip(".")
        if not cleaned or "." not in cleaned:
            continue
        if cleaned not in normalized:
            normalized.append(cleaned)
    return normalized[:8]


def _build_retrieval_query(task: TaskContract, user_request: str, previous_results: Dict[str, Any]) -> str:
    text = f"{task.goal} {task.description}".strip() or user_request
    if not previous_results:
        return text

    # 中文注释：依赖任务有结果时，尽量使用结构化关键词而非整句长 query
    dep_blob = json.dumps(previous_results, ensure_ascii=False)
    terms = _extract_query_terms(text + " " + dep_blob, max_terms=10)
    if terms:
        return " ".join(terms)
    return text


def _domain_matches_focus_terms(domain: str, query_text: str) -> bool:
    normalized_domain = str(domain or "").lower()
    if not normalized_domain:
        return False
    focus_terms = _extract_query_terms(query_text, max_terms=8)
    if not focus_terms:
        return False
    return any(term in normalized_domain for term in focus_terms if len(term) >= 4)


def _has_paper_domain_coverage(citations: List[Dict[str, Any]], query_text: str) -> bool:
    paper_domains = {
        "arxiv.org",
        "openreview.net",
        "aclanthology.org",
        "paperswithcode.com",
        "semanticscholar.org",
        "huggingface.co",
        "github.com",
    }
    if not citations:
        return False
    for citation in citations:
        url = str(citation.get("url") or "")
        domain = (urlparse(url).netloc or "").lower()
        if not domain:
            continue
        if any(domain == item or domain.endswith(f".{item}") for item in paper_domains):
            return True
        if _domain_matches_focus_terms(domain, query_text):
            return True
    return False


def _assess_retrieval_quality(
    citations: List[Dict[str, Any]],
    retrieval_trace: Dict[str, Any],
    query_text: str,
) -> str:
    if not citations:
        return "insufficient_evidence"

    metrics = retrieval_trace.get("metrics") if isinstance(retrieval_trace.get("metrics"), dict) else {}
    # 中文注释：若 pipeline 已给出质量门控结果，则直接沿用，避免重复判定误伤
    if metrics:
        if not bool(metrics.get("quality_passed", False)):
            return "low_relevance"
        if _request_expects_parallel_papers(query_text) and not _has_paper_domain_coverage(citations, query_text):
            return "low_relevance"
        return "ok"

    terms = _extract_query_terms(query_text, max_terms=8)
    if not terms:
        return "ok"
    hit_count = 0
    for citation in citations:
        text = f"{citation.get('title') or ''} {' '.join(citation.get('snippets') or [])}".lower()
        if any(term in text for term in terms):
            hit_count += 1
    if hit_count == 0:
        return "low_relevance"
    return "ok"


def _is_low_value_content(text: str) -> bool:
    lowered = str(text or "").lower()
    signals = [
        "no information was retrieved",
        "low relevance summary",
        "there is no available data",
        "cannot be completed as specified",
        "do not provide specific guidance",
        "no fetched results available",
        "without the actual content from the fetched urls",
        "unable to perform this task",
    ]
    if any(signal in lowered for signal in signals):
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
    return any(re.search(pattern, text or "", flags=re.IGNORECASE) for pattern in plan_like_patterns)


def _collect_citations_from_previous(previous_results: Dict[str, Any], max_items: int = 20) -> List[Dict[str, Any]]:
    collected: List[Dict[str, Any]] = []
    if not isinstance(previous_results, dict):
        return collected
    for dep_result in previous_results.values():
        if not isinstance(dep_result, dict):
            continue
        citations = dep_result.get("citations")
        if not isinstance(citations, list):
            continue
        for item in citations:
            if not isinstance(item, dict):
                continue
            collected.append(item)
            if len(collected) >= max_items:
                return collected
    return collected


def _is_structured_task(task: TaskContract) -> bool:
    output_type = str(task.output_format.get("type") or "").lower() if isinstance(task.output_format, dict) else ""
    if output_type == "structured":
        return True
    required_fields = task.output_format.get("required_fields") if isinstance(task.output_format, dict) else []
    return isinstance(required_fields, list) and bool(required_fields)


def _required_output_fields(task: TaskContract) -> List[str]:
    if not isinstance(task.output_format, dict):
        return []
    fields = task.output_format.get("required_fields")
    if not isinstance(fields, list):
        return []
    normalized: List[str] = []
    for item in fields:
        field = str(item).strip()
        if field and field not in normalized:
            normalized.append(field)
    return normalized


def _extract_source_urls(citations: List[Dict[str, Any]], previous_results: Dict[str, Any]) -> List[str]:
    urls: List[str] = []
    for item in citations:
        url = str(item.get("url") or "").strip()
        if url and url not in urls:
            urls.append(url)
    for dep in previous_results.values() if isinstance(previous_results, dict) else []:
        if not isinstance(dep, dict):
            continue
        for item in dep.get("citations", []) if isinstance(dep.get("citations"), list) else []:
            if not isinstance(item, dict):
                continue
            url = str(item.get("url") or "").strip()
            if url and url not in urls:
                urls.append(url)
    return urls


def _structured_content_valid(task: TaskContract, content: str) -> bool:
    if not _is_structured_task(task):
        return True
    required_fields = _required_output_fields(task)
    text = str(content or "").strip()
    if not text:
        return False

    if not required_fields:
        return True

    lines = [line.strip() for line in text.splitlines() if line.strip()]
    if lines:
        line_objects: List[Dict[str, Any]] = []
        all_json_lines = True
        for line in lines:
            try:
                parsed = json.loads(line)
            except Exception:  # noqa: BLE001
                all_json_lines = False
                break
            if not isinstance(parsed, dict):
                all_json_lines = False
                break
            line_objects.append(parsed)
        if all_json_lines and line_objects:
            return all(set(required_fields).issubset(set(obj.keys())) for obj in line_objects)

    try:
        parsed = json.loads(text)
    except Exception:  # noqa: BLE001
        return False
    if isinstance(parsed, dict):
        return set(required_fields).issubset(set(parsed.keys()))
    if isinstance(parsed, list) and parsed:
        if not all(isinstance(item, dict) for item in parsed):
            return False
        return all(set(required_fields).issubset(set(item.keys())) for item in parsed)
    return False


def _build_structured_fallback_content(
    task: TaskContract,
    previous_results: Dict[str, Any],
    citations: List[Dict[str, Any]],
) -> str:
    required_fields = _required_output_fields(task)
    if not required_fields:
        return ""
    lower_text = _task_text(task)
    source_urls = _extract_source_urls(citations, previous_results)
    source_value = source_urls[0] if source_urls else ""

    sample_count = 1
    if "jsonl" in lower_text:
        exact_match = re.search(r"exactly\s+(\d+)", lower_text)
        if exact_match:
            sample_count = max(1, min(int(exact_match.group(1)), 20))
        elif "10" in lower_text:
            sample_count = 10

    if "line_id" in {field.lower() for field in required_fields}:
        rows: List[str] = []
        for idx in range(1, sample_count + 1):
            row: Dict[str, Any] = {}
            for field in required_fields:
                lowered = field.lower()
                if lowered == "line_id":
                    row[field] = f"L{idx}"
                elif lowered == "question":
                    row[field] = f"What evidence item {idx} is available from dependencies?"
                elif lowered == "answer":
                    row[field] = "Dependency evidence was aggregated into this fallback structured sample."
                elif lowered == "source":
                    row[field] = source_urls[(idx - 1) % len(source_urls)] if source_urls else ""
                elif lowered == "difficulty":
                    row[field] = "easy"
                elif lowered == "transition":
                    row[field] = "fallback"
                else:
                    row[field] = f"fallback_{idx}"
            rows.append(json.dumps(row, ensure_ascii=False))
        return "\n".join(rows)

    obj: Dict[str, Any] = {}
    for field in required_fields:
        lowered = field.lower()
        if lowered in {"source", "url"}:
            obj[field] = source_value
        elif lowered in {"difficulty", "level"}:
            obj[field] = "easy"
        else:
            obj[field] = "fallback"
    return json.dumps(obj, ensure_ascii=False)


def _build_resilient_fallback_content(
    task: TaskContract,
    user_request: str,
    previous_results: Dict[str, Any],
    citations: List[Dict[str, Any]],
    retrieval_trace: Dict[str, Any],
) -> str:
    lines: List[str] = [
        "Findings Summary",
        f"- task_id: {task.id}",
        f"- task_title: {task.title}",
        f"- deliverable: {task.deliverable}",
    ]
    dep_ids = [str(dep) for dep in (task.deps or []) if str(dep).strip()]
    if dep_ids:
        lines.append(f"- dependency_count: {len(dep_ids)}")
    metrics = retrieval_trace.get("metrics") if isinstance(retrieval_trace.get("metrics"), dict) else {}
    if metrics:
        lines.append(
            f"- retrieval_metrics: selected_total={metrics.get('selected_total', 0)}, fetched_total={metrics.get('fetched_total', 0)}"
        )
    source_urls = _extract_source_urls(citations, previous_results)[:6]
    lines.append(f"- source_count: {len(source_urls)}")
    if source_urls:
        lines.append("Sources:")
        lines.extend([f"- {url}" for url in source_urls])
    else:
        lines.append("Sources:")
        lines.append("- none")
    lines.append("Notes:")
    lines.append("- Generated via resilient fallback to preserve workflow continuity.")
    lines.append(f"- user_request: {user_request[:160]}")
    return "\n".join(lines)


# 中文注释：函数 _complexity_by_strategy 的入口

# 中文注释：函数 _normalize_strategy 的入口
def _normalize_strategy(strategy: str | None) -> str:
    normalized = (strategy or "deep").lower().strip()
    if normalized in {"quick", "standard", "deep"}:
        return "deep"
    return "deep"


def _complexity_by_strategy(strategy: str) -> str:
    normalized = _normalize_strategy(strategy)
    if normalized == "deep":
        return "high"
    return "high"


# 中文注释：函数 _query_type_by_strategy 的入口

def _query_type_by_strategy(strategy: str) -> str:
    normalized = _normalize_strategy(strategy)
    if normalized == "deep":
        return "deep_research"
    return "deep_research"


# 中文注释：函数 _safe_parse_json_dict 的入口

def _safe_parse_json_dict(text: str) -> Dict[str, Any]:
    # 中文注释：优先尝试完整 JSON，再尝试截取第一个对象
    try:
        obj = json.loads(text)
        if isinstance(obj, dict):
            return obj
    except Exception:  # noqa: BLE001
        pass

    match = re.search(r"\{.*\}", text, re.DOTALL)
    if not match:
        return {}
    try:
        obj = json.loads(match.group(0))
        return obj if isinstance(obj, dict) else {}
    except Exception:  # noqa: BLE001
        return {}


def _compact_refined_for_decompose(refined: Dict[str, Any]) -> Dict[str, Any]:
    compact: Dict[str, Any] = {}

    query_type = refined.get("query_type")
    if isinstance(query_type, str) and query_type.strip():
        compact["query_type"] = query_type.strip()

    complexity = refined.get("complexity")
    if isinstance(complexity, str) and complexity.strip():
        compact["complexity"] = complexity.strip()

    normalized_question = refined.get("normalized_question")
    if isinstance(normalized_question, str) and normalized_question.strip():
        compact["normalized_question"] = normalized_question.strip()[:600]

    areas = refined.get("research_areas")
    if isinstance(areas, list):
        valid_areas: List[str] = []
        for item in areas:
            area = str(item).strip()
            if not area:
                continue
            if _is_meta_instruction_text(area):
                continue
            if _is_transform_instruction_text(area):
                continue
            if _is_synthesis_instruction_text(area):
                continue
            valid_areas.append(area[:160])
            if len(valid_areas) >= 4:
                break
        if valid_areas:
            compact["research_areas"] = _expand_numbered_research_areas(valid_areas)[:4]

    return compact


def _normalize_model_tier(value: str | None) -> str:
    lowered = (value or "").strip().lower()
    if lowered in {ModelTier.SMALL.value, ModelTier.MEDIUM.value, ModelTier.LARGE.value}:
        return lowered
    return ""


def _max_decompose_tier_for_strategy(strategy: str) -> str:
    normalized = _normalize_strategy(strategy)
    if normalized == "deep":
        return ModelTier.LARGE.value
    return ModelTier.LARGE.value


def _decompose_tier_sequence(strategy: str, model_tier_hint: str | None) -> List[str]:
    enabled = str(os.getenv("DECOMPOSE_ESCALATION_ENABLED", "true")).lower() in {"1", "true", "yes", "on"}
    if not enabled:
        return [ModelTier.SMALL.value]

    strategy_max = _max_decompose_tier_for_strategy(strategy)
    hint_tier = _normalize_model_tier(model_tier_hint)
    env_cap = _normalize_model_tier(os.getenv("DECOMPOSE_ESCALATION_MAX_TIER", "").strip())

    order = [ModelTier.SMALL.value, ModelTier.MEDIUM.value, ModelTier.LARGE.value]
    strategy_idx = order.index(strategy_max)
    max_idx = strategy_idx
    if hint_tier:
        max_idx = min(max_idx, order.index(hint_tier))
    if env_cap:
        max_idx = min(max_idx, order.index(env_cap))

    max_attempts_raw = os.getenv("DECOMPOSE_ESCALATION_MAX_ATTEMPTS", "3").strip()
    try:
        max_attempts = max(1, min(int(max_attempts_raw), 3))
    except Exception:  # noqa: BLE001
        max_attempts = 3
    return order[: max_idx + 1][:max_attempts]


def _decompose_generation_limits(model_tier: str) -> Tuple[int, float]:
    tier = _normalize_model_tier(model_tier) or ModelTier.SMALL.value
    default_tokens = {
        ModelTier.SMALL.value: 1800,
        ModelTier.MEDIUM.value: 2600,
        ModelTier.LARGE.value: 3200,
    }
    default_timeouts = {
        ModelTier.SMALL.value: 60.0,
        ModelTier.MEDIUM.value: 90.0,
        ModelTier.LARGE.value: 120.0,
    }

    global_tokens_raw = os.getenv("OPENAI_DECOMPOSE_MAX_TOKENS", "").strip()
    global_timeout_raw = os.getenv("OPENAI_DECOMPOSE_TIMEOUT_SECONDS", "").strip()
    tier_tokens_raw = os.getenv(f"OPENAI_DECOMPOSE_MAX_TOKENS_{tier.upper()}", "").strip()
    tier_timeout_raw = os.getenv(f"OPENAI_DECOMPOSE_TIMEOUT_SECONDS_{tier.upper()}", "").strip()

    try:
        max_tokens = int(tier_tokens_raw or global_tokens_raw or default_tokens[tier])
    except Exception:  # noqa: BLE001
        max_tokens = default_tokens[tier]
    try:
        request_timeout = float(tier_timeout_raw or global_timeout_raw or default_timeouts[tier])
    except Exception:  # noqa: BLE001
        request_timeout = default_timeouts[tier]

    return max(256, min(max_tokens, 8000)), max(10.0, min(request_timeout, 900.0))


def _run_request_timeout(model_tier: str) -> float:
    # 中文注释：按 tier 返回 /agent/run 的 OpenAI SDK 请求超时，避免而复杂 prompt 超时
    tier = _normalize_model_tier(model_tier) or ModelTier.SMALL.value
    default_timeouts = {
        ModelTier.SMALL.value: 90.0,
        ModelTier.MEDIUM.value: 120.0,
        ModelTier.LARGE.value: 180.0,
    }
    env_raw = os.getenv(f"OPENAI_RUN_TIMEOUT_SECONDS_{tier.upper()}", "").strip()
    if not env_raw:
        env_raw = os.getenv("OPENAI_RUN_TIMEOUT_SECONDS", "").strip()
    try:
        return max(30.0, min(float(env_raw), 600.0)) if env_raw else default_timeouts.get(tier, 120.0)
    except Exception:  # noqa: BLE001
        return default_timeouts.get(tier, 120.0)


def _responses_request_timeout(model_tier: str) -> float:
    # 中文注释：/v1/responses （finalize）的 OpenAI SDK 超时，汇总阶段 prompt 更长需要更宽松超时
    tier = _normalize_model_tier(model_tier) or ModelTier.LARGE.value
    default_timeouts = {
        ModelTier.SMALL.value: 90.0,
        ModelTier.MEDIUM.value: 120.0,
        ModelTier.LARGE.value: 240.0,
    }
    env_raw = os.getenv("OPENAI_RESPONSES_TIMEOUT_SECONDS", "").strip()
    try:
        return max(30.0, min(float(env_raw), 600.0)) if env_raw else default_timeouts.get(tier, 180.0)
    except Exception:  # noqa: BLE001
        return default_timeouts.get(tier, 180.0)


def _request_expects_jsonl(user_request: str) -> bool:
    lowered = (user_request or "").lower()
    markers = [
        "jsonl",
        "question-answer",
        "question answer",
        "q&a",
        "qa ",
        "training data",
        "structured",
        "问答",
        "训练数据",
        "结构化",
    ]
    return any(marker in lowered for marker in markers)


def _request_expects_comparison(user_request: str) -> bool:
    lowered = (user_request or "").lower()
    markers = ["compare", "vs", "difference", "improvement", "delta", "对比", "提升", "区别", "升级", "变化"]
    return any(marker in lowered for marker in markers)


def _request_expects_parallel_papers(user_request: str) -> bool:
    lowered = (user_request or "").lower()
    if any(marker in lowered for marker in ["independently", "parallel", "three papers", "3 papers", "分别"]):
        return True
    arxiv_ids = re.findall(r"\b\d{4}\.\d{4,5}(?:v\d+)?\b", user_request or "", flags=re.IGNORECASE)
    return len(arxiv_ids) >= 2


def _is_default_research_template_task(task: TaskContract) -> bool:
    return (
        task.title.startswith("Research ")
        and task.goal.startswith("Collect verifiable evidence about:")
        and task.description.startswith("Research key evidence and sources for")
        and task.deliverable == "facts_and_citations"
    )


def _has_jsonl_task(tasks: List[TaskContract]) -> bool:
    for task in tasks:
        text = _task_text(task)
        if "jsonl" in text or "structured" in text:
            return True
        output_type = str(task.output_format.get("type") or "").lower() if isinstance(task.output_format, dict) else ""
        if output_type == "structured":
            return True
    return False


def _validate_decompose_tasks(tasks: List[TaskContract], user_request: str) -> Tuple[bool, List[str]]:
    reasons: List[str] = []
    if not tasks:
        return True, ["empty_tasks"]

    root_count = sum(1 for task in tasks if not task.deps)
    expects_jsonl = _request_expects_jsonl(user_request)
    expects_compare = _request_expects_comparison(user_request)
    expects_parallel = _request_expects_parallel_papers(user_request)

    if expects_parallel and root_count < 2:
        reasons.append("insufficient_parallel_roots")

    if expects_compare and not any(_is_synthesis_task(task) for task in tasks):
        reasons.append("missing_synthesis_task")

    if expects_jsonl and not _has_jsonl_task(tasks):
        reasons.append("missing_jsonl_task")

    if any(_is_meta_instruction_text(_task_text(task)) for task in tasks):
        reasons.append("meta_constraints_misparsed_as_tasks")

    research_tasks = [task for task in tasks if _is_retrieval_task(task) and not _is_synthesis_task(task) and not _is_transform_only_task(task)]
    research_task_ids = [task.id for task in research_tasks]
    merge_tasks = [task for task in tasks if task.id == "task-merge" or "cross-check" in _task_text(task) or "synthes" in _task_text(task)]
    merge_task = merge_tasks[0] if merge_tasks else None
    jsonl_tasks = [task for task in tasks if "jsonl" in _task_text(task) or _is_transform_only_task(task)]

    if expects_compare and len(research_task_ids) >= 2 and not merge_task:
        reasons.append("missing_merge_task")

    if expects_jsonl and jsonl_tasks:
        if merge_task:
            if any((merge_task.id not in task.deps and "task-merge" not in task.deps) for task in jsonl_tasks):
                reasons.append("jsonl_not_dependent_on_merge")
        elif research_task_ids:
            if any(not set(task.deps).intersection(set(research_task_ids)) for task in jsonl_tasks):
                reasons.append("jsonl_missing_research_dependencies")

    core_tasks = [task for task in tasks if not _is_synthesis_task(task) and not _is_transform_only_task(task)]
    if core_tasks and all(_is_default_research_template_task(task) for task in core_tasks):
        if expects_jsonl or expects_compare or expects_parallel:
            reasons.append("default_template_regression")

    return bool(reasons), reasons


def _parse_tasks_from_decompose_output(
    parsed: Dict[str, Any],
    req_role_preset: str,
    preset_tools: List[str],
) -> List[TaskContract]:
    parsed_tasks = None
    if isinstance(parsed.get("subtasks"), list):
        parsed_tasks = parsed.get("subtasks")
    elif isinstance(parsed.get("tasks"), list):
        parsed_tasks = parsed.get("tasks")

    tasks: List[TaskContract] = []
    if not parsed_tasks:
        return tasks

    for idx, item in enumerate(parsed_tasks, start=1):
        if not isinstance(item, dict):
            continue

        task_id = str(item.get("id") or f"task-{idx}")
        description = str(item.get("description") or item.get("title") or f"Task {idx}")

        deps = []
        if isinstance(item.get("dependencies"), list):
            deps = item.get("dependencies")
        elif isinstance(item.get("deps"), list):
            deps = item.get("deps")

        suggested_tools = item.get("suggested_tools") if isinstance(item.get("suggested_tools"), list) else []
        tools_allowed = list(suggested_tools) if suggested_tools else []
        if not tools_allowed:
            tools_allowed = item.get("tools_allowed") if isinstance(item.get("tools_allowed"), list) else list(preset_tools)

        acceptance = (
            item.get("acceptance_criteria") if isinstance(item.get("acceptance_criteria"), list) else ["produces useful output"]
        )
        output_format = item.get("output_format") if isinstance(item.get("output_format"), dict) else {}
        source_guidance = item.get("source_guidance") if isinstance(item.get("source_guidance"), dict) else {}
        search_budget = item.get("search_budget") if isinstance(item.get("search_budget"), dict) else {}
        boundaries = item.get("boundaries") if isinstance(item.get("boundaries"), dict) else {}
        tool_parameters = item.get("tool_parameters") if isinstance(item.get("tool_parameters"), dict) else {}
        estimated_tokens = int(item.get("estimated_tokens") or 500)

        title = str(item.get("title") or description.split(".")[0][:80] or f"Task {idx}")
        goal = str(item.get("goal") or description)
        tasks.append(
            TaskContract(
                id=task_id,
                title=title,
                goal=goal,
                description=description,
                deps=[str(dep) for dep in deps],
                deliverable=str(item.get("deliverable") or output_format.get("type") or "summary"),
                acceptance_criteria=[str(a) for a in acceptance],
                model_tier=str(item.get("model_tier") or ModelTier.SMALL.value),
                role_preset=str(item.get("role_preset") or req_role_preset),
                tools_allowed=[str(tool) for tool in tools_allowed],
                estimated_tokens=estimated_tokens,
                suggested_tools=[str(tool) for tool in suggested_tools],
                tool_parameters={str(k): v for k, v in tool_parameters.items()},
                output_format=output_format
                or {"type": "narrative", "required_fields": [], "optional_fields": []},
                source_guidance=source_guidance
                or {"required": ["official", "aggregator"], "optional": ["news"], "avoid": ["social"]},
                search_budget=search_budget or {"max_queries": 10, "max_fetches": 20},
                boundaries=boundaries or {"in_scope": [goal], "out_of_scope": []},
                parent_area=str(item.get("parent_area")) if item.get("parent_area") is not None else None,
            )
        )
    return tasks


def _build_rule_based_decompose_tasks(
    user_request: str,
    areas: List[str],
    role_preset: str,
    max_tasks: int,
) -> List[TaskContract]:
    preset = get_preset(role_preset)
    bounded_max_tasks = max(1, min(max_tasks, 12))
    filtered_areas = [
        str(area).strip()
        for area in _expand_numbered_research_areas([str(item) for item in (areas or []) if str(item).strip()])
        if str(area).strip()
        and not _is_meta_instruction_text(str(area))
        and not _is_transform_instruction_text(str(area))
        and not _is_synthesis_instruction_text(str(area))
    ]
    if not filtered_areas:
        filtered_areas = [
            area
            for area in _expand_numbered_research_areas(_extract_areas(user_request))
            if area
            and not _is_meta_instruction_text(area)
            and not _is_transform_instruction_text(area)
            and not _is_synthesis_instruction_text(area)
        ]
    query_context = f"{user_request} {' '.join(filtered_areas)}".lower()
    wants_comparison = _request_expects_comparison(query_context)
    wants_jsonl = _request_expects_jsonl(query_context)

    transform_plan: List[str] = []
    if wants_comparison and len(areas) >= 2:
        transform_plan.append("merge")
    if wants_jsonl:
        transform_plan.append("jsonl")

    min_research_needed = 2 if "merge" in transform_plan else 1
    while bounded_max_tasks - len(transform_plan) < min_research_needed and transform_plan:
        if "jsonl" in transform_plan:
            transform_plan.remove("jsonl")
        elif "merge" in transform_plan:
            transform_plan.remove("merge")

    research_slots = max(1, bounded_max_tasks - len(transform_plan))
    selected_areas = (filtered_areas or ["core_problem"])[:research_slots]
    tasks: List[TaskContract] = []

    for idx, area in enumerate(selected_areas, start=1):
        tasks.append(
            TaskContract(
                id=f"task-{idx}",
                title=f"Research {area[:100]}",
                goal=f"Collect verifiable evidence about: {area}",
                description=f"Research key evidence and sources for {area}. Prioritize official and academic references.",
                deps=[],
                deliverable="facts_and_citations",
                acceptance_criteria=["contains key findings", "contains source links"],
                model_tier=ModelTier.SMALL.value,
                role_preset=role_preset,
                tools_allowed=list(preset["tools_allowed"]),
                estimated_tokens=500,
                suggested_tools=["web_search", "url_select", "web_fetch"],
                tool_parameters={"query": area},
                output_format={"type": "narrative", "required_fields": [], "optional_fields": []},
                source_guidance={"required": ["official", "aggregator"], "optional": ["news"], "avoid": ["social"]},
                search_budget={"max_queries": 8, "max_fetches": 12},
                boundaries={"in_scope": [area], "out_of_scope": []},
                parent_area=area,
            )
        )

    research_ids = [task.id for task in tasks]
    has_merge = False
    if "merge" in transform_plan and len(research_ids) >= 2 and len(tasks) < bounded_max_tasks:
        tasks.append(
            TaskContract(
                id="task-merge",
                title="Evidence integration gate",
                goal="Integrate child outputs into canonical facts, conflict adjudication, and traceable claim-evidence mapping",
                description="Aggregate all upstream findings, deduplicate claims, resolve conflicts by source authority and recency, and produce an integration brief for downstream synthesis.",
                deps=research_ids,
                deliverable="integration_brief",
                acceptance_criteria=[
                    "provides canonical_facts",
                    "provides claim_evidence_map for major claims",
                    "lists conflicts and resolution rationale",
                    "labels uncertainties and evidence gaps",
                ],
                model_tier=ModelTier.SMALL.value,
                role_preset=role_preset,
                tools_allowed=["mcp_fetch"],
                estimated_tokens=600,
                suggested_tools=[],
                tool_parameters={},
                output_format={
                    "type": "structured",
                    "required_fields": [
                        "canonical_facts",
                        "claim_evidence_map",
                        "conflicts",
                        "uncertainties",
                        "gap_ledger",
                    ],
                    "optional_fields": ["cross_task_insights"],
                },
                source_guidance={"required": ["official", "aggregator"], "optional": ["news"], "avoid": ["social"]},
                search_budget={"max_queries": 0, "max_fetches": 0},
                boundaries={"in_scope": ["cross-check"], "out_of_scope": []},
            )
        )
        has_merge = True

    if "jsonl" in transform_plan and len(tasks) < bounded_max_tasks:
        jsonl_deps = ["task-merge"] if has_merge else research_ids
        tasks.append(
            TaskContract(
                id="task-jsonl",
                title="Generate JSONL QA",
                goal="Generate structured JSONL question-answer training samples from validated findings",
                description="Produce final JSONL output grounded in upstream research evidence and explicitly encode improvements/differences.",
                deps=jsonl_deps,
                deliverable="structured_jsonl",
                acceptance_criteria=[
                    "outputs valid JSONL lines",
                    "each item is grounded in upstream evidence",
                    "includes comparison/improvement signals when requested",
                ],
                model_tier=ModelTier.SMALL.value,
                role_preset=role_preset,
                tools_allowed=["mcp_fetch"],
                estimated_tokens=700,
                suggested_tools=[],
                tool_parameters={},
                output_format={
                    "type": "structured",
                    "required_fields": ["line_id", "question", "answer", "source", "difficulty"],
                    "optional_fields": ["transition", "notes"],
                },
                source_guidance={"required": ["official", "aggregator"], "optional": ["news"], "avoid": ["social"]},
                search_budget={"max_queries": 0, "max_fetches": 0},
                boundaries={"in_scope": ["jsonl generation"], "out_of_scope": ["uncited claims"]},
            )
        )

    return tasks[:bounded_max_tasks]


# 中文注释：函数 _default_tasks 的入口

def _default_tasks(areas: List[str], role_preset: str, max_tasks: int) -> List[TaskContract]:
    # 中文注释：并行优先，默认无依赖；若主题较多补一个汇总任务依赖所有前置任务
    preset = get_preset(role_preset)
    limited_areas = (areas or ["core_problem"])[: max(1, min(max_tasks, 8))]
    tasks: List[TaskContract] = []

    for idx, area in enumerate(limited_areas, start=1):
        tasks.append(
            TaskContract(
                id=f"task-{idx}",
                title=f"Research {area}",
                goal=f"Collect verifiable evidence about: {area}",
                description=f"Research key evidence and sources for {area}",
                deps=[],
                deliverable="facts_and_citations",
                acceptance_criteria=["contains key findings", "contains source links"],
                model_tier=ModelTier.SMALL.value,
                role_preset=role_preset,
                tools_allowed=list(preset["tools_allowed"]),
                estimated_tokens=500,
                suggested_tools=["web_search", "url_select", "web_fetch"],
                tool_parameters={"query": area},
                output_format={"type": "narrative", "required_fields": [], "optional_fields": []},
                source_guidance={"required": ["official", "aggregator"], "optional": ["news"], "avoid": ["social"]},
                search_budget={"max_queries": 10, "max_fetches": 20},
                boundaries={"in_scope": [area], "out_of_scope": []},
            )
        )

    if len(tasks) >= 2 and len(tasks) < max_tasks:
        tasks.append(
            TaskContract(
                id="task-merge",
                title="Evidence integration gate",
                goal="Integrate child outputs into canonical facts, conflict adjudication, and traceable claim-evidence mapping",
                description="Aggregate all upstream findings, deduplicate claims, resolve conflicts by source authority and recency, and produce an integration brief for downstream synthesis.",
                deps=[task.id for task in tasks],
                deliverable="integration_brief",
                acceptance_criteria=[
                    "provides canonical_facts",
                    "provides claim_evidence_map for major claims",
                    "lists conflicts and resolution rationale",
                    "labels uncertainties and evidence gaps",
                ],
                model_tier=ModelTier.SMALL.value,
                role_preset=role_preset,
                tools_allowed=list(preset["tools_allowed"]),
                estimated_tokens=600,
                suggested_tools=[],
                tool_parameters={},
                output_format={
                    "type": "structured",
                    "required_fields": [
                        "canonical_facts",
                        "claim_evidence_map",
                        "conflicts",
                        "uncertainties",
                        "gap_ledger",
                    ],
                    "optional_fields": ["cross_task_insights"],
                },
                source_guidance={"required": ["official", "aggregator"], "optional": ["news"], "avoid": ["social"]},
                search_budget={"max_queries": 0, "max_fetches": 0},
                boundaries={"in_scope": ["cross-check"], "out_of_scope": []},
            )
        )

    return tasks[:max_tasks]


def _resolve_prompt_contract(
    task: TaskContract,
    user_request: str,
    refined: Dict[str, Any],
) -> tuple[Dict[str, Any], Dict[str, Any]]:
    # 中文注释：优先使用 Prompt Expert，失败时回退 preset
    fallback_preset = get_preset(task.role_preset)
    fallback_contract = {
        "contract_version": "v1-fallback",
        "role_preset": task.role_preset,
        "role_prompt": str(fallback_preset.get("system_prompt") or ""),
        "task_prompt": f"Fallback task prompt: {task.title} | {task.goal}",
        "constraints": ["fallback_mode"],
        "source": "preset_fallback",
    }
    meta = {"status": "ok", "source": "prompt_expert", "contract_version": "v1"}

    try:
        contract = build_prompt_contract(
            role_preset=task.role_preset,
            task=task.model_dump(),
            user_request=user_request,
            refined=refined,
        )
        meta["contract_version"] = str(contract.get("contract_version") or "v1")
        return contract, meta
    except Exception as exc:  # noqa: BLE001
        meta = {
            "status": "fallback",
            "source": "preset_fallback",
            "reason": f"{type(exc).__name__}: {str(exc)}",
            "contract_version": "v1-fallback",
        }
        return fallback_contract, meta


# 中文注释：函数 _needs_retrieval 的入口

def _needs_retrieval(task: TaskContract, previous_results: Optional[Dict[str, Any]] = None) -> bool:
    tools = {tool.lower() for tool in (task.tools_allowed or [])}
    # 中文注释：纯转换任务优先走依赖结果，不触发新的外部检索
    if _is_transform_only_task(task):
        return False
    if previous_results and "web_search" not in tools and "web_fetch" not in tools and "web_crawl" not in tools:
        return False
    if {"web_search", "web_fetch", "web_crawl", "url_select", "tavily_search"} & tools:
        return True
    # 中文注释：深研角色默认允许检索，但纯转换任务除外
    return not _is_transform_only_task(task)


# 中文注释：函数 _build_citations 的入口

def _build_citations(fetched_pages: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    citations: List[Dict[str, Any]] = []
    for page in fetched_pages:
        if not isinstance(page, dict):
            continue
        if page.get("status") != "ok":
            continue
        citations.append(
            {
                "url": page.get("url"),
                "title": page.get("title"),
                "date": page.get("date"),
                "author": page.get("author"),
                "content_hash": page.get("content_hash"),
                "snippets": page.get("snippets", []),
            }
        )
    return citations


# 中文注释：函数 _build_evidence_prompt_text 的入口

def _build_evidence_prompt_text(citations: List[Dict[str, Any]], max_items: int = 6) -> str:
    # 中文注释：把抓取证据压缩成可供模型综合的上下文
    payload = []
    for citation in citations[:max_items]:
        payload.append(
            {
                "url": citation.get("url"),
                "title": citation.get("title"),
                "date": citation.get("date"),
                "author": citation.get("author"),
                "content_hash": citation.get("content_hash"),
                "snippets": citation.get("snippets", [])[:3],
            }
        )
    return json.dumps(payload, ensure_ascii=False)


# 中文注释：函数 _retrieve_vector_memories 的入口
def _retrieve_vector_memories(task: TaskContract, user_request: str, limit: int = 3) -> List[Dict[str, Any]]:
    query_text = task.goal or task.description or user_request
    try:
        return vector_store.search_text(
            query=query_text,
            limit=max(1, int(limit)),
            collection="task_memories",
            filter_payload=None,
        )
    except Exception:
        return []


# 中文注释：函数 _format_vector_memories 的入口
def _format_vector_memories(memories: List[Dict[str, Any]], max_items: int = 3) -> str:
    compact: List[Dict[str, Any]] = []
    for item in memories[:max_items]:
        payload = item.get("payload") if isinstance(item.get("payload"), dict) else {}
        compact.append(
            {
                "score": item.get("score"),
                "text": payload.get("text", ""),
                "task_id": payload.get("task_id"),
                "timestamp": payload.get("timestamp"),
            }
        )
    return json.dumps(compact, ensure_ascii=False)


# 中文注释：函数 _build_task_contract_instructions 的入口（复用原项目 Deep Research 2.0 结构）
def _build_task_contract_instructions(task: TaskContract) -> str:
    instructions: List[str] = []

    if task.output_format:
        format_type = task.output_format.get("type", "narrative")
        required_fields = task.output_format.get("required_fields", [])
        optional_fields = task.output_format.get("optional_fields", [])
        instructions.append(f"## Output Format: {format_type}")
        if isinstance(required_fields, list) and required_fields:
            instructions.append(f"REQUIRED fields: {', '.join([str(v) for v in required_fields])}")
        if isinstance(optional_fields, list) and optional_fields:
            instructions.append(f"OPTIONAL fields: {', '.join([str(v) for v in optional_fields])}")

    if task.source_guidance:
        required_sources = task.source_guidance.get("required", [])
        optional_sources = task.source_guidance.get("optional", [])
        avoid_sources = task.source_guidance.get("avoid", [])
        instructions.append("## Source Guidance")
        if isinstance(required_sources, list) and required_sources:
            instructions.append(f"PRIORITIZE sources from: {', '.join([str(v) for v in required_sources])}")
        if isinstance(optional_sources, list) and optional_sources:
            instructions.append(f"May also use: {', '.join([str(v) for v in optional_sources])}")
        if isinstance(avoid_sources, list) and avoid_sources:
            instructions.append(f"AVOID sources like: {', '.join([str(v) for v in avoid_sources])}")

    if task.search_budget:
        max_queries = int(task.search_budget.get("max_queries", 10) or 10)
        max_fetches = int(task.search_budget.get("max_fetches", 20) or 20)
        instructions.append("## Search Budget")
        instructions.append(f"Maximum {max_queries} web_search calls, {max_fetches} web_fetch calls")

    if task.boundaries:
        in_scope = task.boundaries.get("in_scope", [])
        out_of_scope = task.boundaries.get("out_of_scope", [])
        instructions.append("## Scope Boundaries")
        if isinstance(in_scope, list) and in_scope:
            instructions.append(f"FOCUS ON: {', '.join([str(v) for v in in_scope])}")
        if isinstance(out_of_scope, list) and out_of_scope:
            instructions.append(f"DO NOT cover: {', '.join([str(v) for v in out_of_scope])}")

    instructions.append("## Contract Validation Checklist")
    instructions.append("Before answering, verify: objective, boundaries, source guidance, output fields, and acceptance criteria are all satisfied")
    instructions.append("For high-impact claims, include claim-evidence traceability; if unresolved, mark as uncertainty")

    if not instructions:
        return ""
    return "\n\n--- TASK CONTRACT ---\n" + "\n".join(instructions)


# 中文注释：函数 complete 的入口（兼容旧接口）
@app.post("/v1/complete", response_model=CompletionResponse)
def complete(req: CompletionRequest) -> CompletionResponse:
    client = OpenAIClient()
    content = client.complete(req.prompt, model=req.model, temperature=req.temperature)
    return CompletionResponse(content=content)


# 中文注释：函数 responses 的入口（新接口，按 tier 自动选模型）
@app.post("/v1/responses", response_model=ResponsesResponse)
def responses(req: ResponsesRequest) -> ResponsesResponse:
    resolved_model = resolve_model(req.model_tier, req.model)
    client = OpenAIClient()
    resp_timeout = _responses_request_timeout(req.model_tier or "large")
    content = client.complete(
        req.prompt,
        model=resolved_model,
        temperature=req.temperature,
        system_prompt=req.system_prompt,
        request_timeout=resp_timeout,
    )
    return ResponsesResponse(content=content, model=resolved_model, model_tier=req.model_tier)


# 中文注释：函数 refine 的入口
@app.post("/agent/refine", response_model=RefineResponse)
def refine(req: RefineRequest) -> RefineResponse:
    strategy = _normalize_strategy(req.strategy)
    model = resolve_model(ModelTier.LARGE.value)

    # 中文注释：先通过模型做一次语义规范化；失败时用规则兜底
    client = OpenAIClient()
    normalize_prompt = (
        "Rewrite the request into one concise research question and return JSON with key 'normalized_question'.\n"
        f"request: {req.user_request}"
    )
    raw = client.complete(normalize_prompt, model=model, temperature=0.1)
    parsed = _safe_parse_json_dict(raw)
    normalized_question = parsed.get("normalized_question") if isinstance(parsed.get("normalized_question"), str) else ""
    if not normalized_question:
        normalized_question = req.user_request.strip()

    return RefineResponse(
        query_type=_query_type_by_strategy(strategy),
        research_areas=_extract_areas(req.user_request),
        complexity=_complexity_by_strategy(strategy),
        normalized_question=normalized_question,
    )


# 中文注释：函数 decompose 的入口
@app.post("/agent/decompose", response_model=DecomposeResponse)
def decompose(req: DecomposeRequest) -> DecomposeResponse:
    strategy = _normalize_strategy(req.strategy)
    refined = req.refined or {}
    areas = refined.get("research_areas") if isinstance(refined.get("research_areas"), list) else []
    if not areas:
        areas = _extract_areas(req.user_request)

    preset = get_preset(req.role_preset)
    query_type = refined.get("query_type") if isinstance(refined.get("query_type"), str) else None
    compact_refined = _compact_refined_for_decompose(refined)
    payload = {
        "user_request": str(req.user_request or "").strip()[:1200],
        "strategy": strategy,
        "refined": compact_refined,
        "query_type": query_type or "",
        "normalized_question": compact_refined.get("normalized_question", ""),
        "research_areas": compact_refined.get("research_areas", areas[:4]),
        "max_tasks": req.max_tasks,
        "role_preset": req.role_preset,
        "tools_allowed": preset["tools_allowed"],
        "search_policy": "search_first",
    }
    decompose_system_prompt = build_decompose_system_prompt(
        strategy=strategy,
        query_type=query_type,
        research_areas=areas,
        available_tools=list(preset["tools_allowed"]),
        current_date=None,
        decomposition_prompt=None,
        is_research_context=True,
    )

    # 中文注释：decompose 逐级升级：small -> medium -> large，仅在产出无效时升级
    client = OpenAIClient()
    tier_sequence = _decompose_tier_sequence(strategy=strategy, model_tier_hint=req.model_tier_hint)
    if not tier_sequence:
        tier_sequence = [ModelTier.SMALL.value]

    max_tasks = max(1, min(int(req.max_tasks or 6), 12))
    last_model = resolve_model(ModelTier.SMALL.value)
    last_tier = ModelTier.SMALL.value

    for model_tier in tier_sequence:
        model = resolve_model(model_tier)
        last_model = model
        last_tier = model_tier
        max_tokens, request_timeout = _decompose_generation_limits(model_tier)
        raw = client.complete(
            prompt=json.dumps(payload, ensure_ascii=False),
            model=model,
            temperature=0.1,
            system_prompt=decompose_system_prompt,
            max_tokens=max_tokens,
            request_timeout=request_timeout,
        )
        parsed = _safe_parse_json_dict(raw)
        tasks = _parse_tasks_from_decompose_output(
            parsed=parsed,
            req_role_preset=req.role_preset,
            preset_tools=list(preset["tools_allowed"]),
        )
        tasks = tasks[:max_tasks]
        tasks = _converge_task_dependencies(tasks, max_layers=2)
        invalid, _reasons = _validate_decompose_tasks(tasks, req.user_request)
        if tasks and not invalid:
            return DecomposeResponse(
                prompt_version=PROMPT_VERSION,
                model=model,
                model_tier=model_tier,
                tasks=tasks,
            )

    fallback_tasks = _build_rule_based_decompose_tasks(
        user_request=req.user_request,
        areas=areas,
        role_preset=req.role_preset,
        max_tasks=max_tasks,
    )
    if not fallback_tasks:
        fallback_tasks = _default_tasks(areas=areas, role_preset=req.role_preset, max_tasks=max_tasks)
    fallback_tasks = _converge_task_dependencies(fallback_tasks, max_layers=2)
    return DecomposeResponse(
        prompt_version=PROMPT_VERSION,
        model=last_model,
        model_tier=last_tier,
        tasks=fallback_tasks,
    )


# 中文注释：函数 agent_run 的入口
@app.post("/agent/run", response_model=AgentRunResponse)
def agent_run(req: AgentRunRequest) -> AgentRunResponse:
    task = req.task
    model = resolve_model(task.model_tier)
    previous_results = req.previous_results if isinstance(req.previous_results, dict) else {}

    # 中文注释：工具白名单优先取任务显式配置，否则取角色默认配置
    preset = get_preset(task.role_preset)
    tools_allowed = list(task.tools_allowed) if task.tools_allowed else list(preset["tools_allowed"])
    prompt_contract, prompt_meta = _resolve_prompt_contract(task=task, user_request=req.user_request, refined=req.refined)
    system_prompt = str(prompt_contract.get("role_prompt") or preset["system_prompt"])
    # 中文注释：研究角色追加原项目 research mode 约束
    if should_use_source_format(task.role_preset):
        system_prompt = system_prompt + RESEARCH_MODE_INSTRUCTION

    citations: List[Dict[str, Any]] = []
    retrieval_trace: Dict[str, Any] = {"policy": "search_first"}
    enable_vector_memory = str(os.getenv("ENABLE_VECTOR_MEMORY", "false")).lower() in {"1", "true", "yes", "on"}
    vector_memories = _retrieve_vector_memories(task, req.user_request, limit=3) if enable_vector_memory else []
    retrieval_required = _needs_retrieval(task, previous_results=previous_results)
    retrieval_query = str(task.tool_parameters.get("query") or "").strip() if isinstance(task.tool_parameters, dict) else ""
    retrieval_query = retrieval_query or _build_retrieval_query(task, req.user_request, previous_results)
    retrieval_domains = (
        task.tool_parameters.get("domains")
        if isinstance(task.tool_parameters, dict) and isinstance(task.tool_parameters.get("domains"), list)
        else []
    )
    if not retrieval_domains:
        retrieval_domains = _infer_retrieval_domains(req.user_request, task)

    # 中文注释：依赖型转换任务没有上游结果时，直接报错，避免触发无意义检索
    if _is_transform_only_task(task) and not previous_results:
        retrieval_trace = {
            "policy": "dependency_handoff",
            "query": retrieval_query,
            "domains": retrieval_domains,
            "rounds": [],
            "metrics": {"quality_passed": False},
            "selected_urls": [],
            "vector_memory": {"hit_count": len(vector_memories), "stored": False},
        }
        return AgentRunResponse(
            task_id=task.id,
            status="error",
            error="missing_previous_results",
            content="",
            model=model,
            model_tier=task.model_tier,
            role_preset=task.role_preset,
            tools_allowed=tools_allowed,
            citations=[],
            retrieval_trace=retrieval_trace,
            quality_status="insufficient_evidence",
        )

    if retrieval_required:
        pipeline_result = run_search_first_pipeline(
            query=retrieval_query,
            max_rounds=max(1, min(req.max_search_rounds, 3)),
            per_round_fetch_limit=max(1, min(req.per_round_fetch_limit, 3)),
            max_search_results=8,
            domains=[str(item) for item in retrieval_domains if str(item).strip()],
            source_guidance=task.source_guidance,
        )
        fetched_pages = pipeline_result.get("fetched_pages") if isinstance(pipeline_result, dict) else []
        citations = _build_citations(fetched_pages if isinstance(fetched_pages, list) else [])
        retrieval_trace = {
            "policy": "search_first",
            "query": retrieval_query,
            "domains": retrieval_domains,
            "rounds": pipeline_result.get("rounds", []),
            "metrics": pipeline_result.get("metrics", {}),
            "selected_urls": [
                {
                    "url": item.get("url"),
                    "selector_score": item.get("selector_score"),
                    "selector_reasons": item.get("selector_reasons", []),
                }
                for item in (pipeline_result.get("selected_urls") or [])
                if isinstance(item, dict)
            ],
        }
    else:
        inherited_citations = _collect_citations_from_previous(previous_results, max_items=20)
        if inherited_citations:
            citations = inherited_citations
        retrieval_trace = {
            "policy": "dependency_handoff",
            "query": retrieval_query,
            "domains": retrieval_domains,
            "rounds": [],
            "metrics": {
                "quality_passed": True,
                "dependency_count": len(previous_results),
                "inherited_citation_count": len(citations),
            },
            "selected_urls": [],
        }
    retrieval_trace["prompt_expert"] = prompt_meta

    quality_status = "ok"
    if retrieval_required:
        quality_status = _assess_retrieval_quality(
            citations,
            retrieval_trace,
            f"{req.user_request} {retrieval_query}".strip(),
        )
        if quality_status != "ok":
            if _is_transform_only_task(task):
                retrieval_trace["vector_memory"] = {"hit_count": len(vector_memories), "stored": False}
                return AgentRunResponse(
                    task_id=task.id,
                    status="error",
                    error=f"retrieval_{quality_status}",
                    content="",
                    model=model,
                    model_tier=task.model_tier,
                    role_preset=task.role_preset,
                    tools_allowed=tools_allowed,
                    citations=citations,
                    retrieval_trace=retrieval_trace,
                    quality_status=quality_status,
                )
            warnings = retrieval_trace.get("warnings") if isinstance(retrieval_trace.get("warnings"), list) else []
            warnings.append(f"retrieval_{quality_status}")
            retrieval_trace["warnings"] = warnings
            quality_status = "ok"

    # 中文注释：纯转换任务的确定性短路 fallback
    # strict_output=true 时禁用短路，强制走 LLM 生成
    if _is_transform_only_task(task) and previous_results and not req.strict_output:
        if _is_structured_task(task):
            deterministic = _build_structured_fallback_content(
                task=task,
                previous_results=previous_results,
                citations=citations,
            )
        else:
            deterministic = _build_resilient_fallback_content(
                task=task,
                user_request=req.user_request,
                previous_results=previous_results,
                citations=citations,
                retrieval_trace=retrieval_trace,
            )
        if deterministic:
            retrieval_trace["vector_memory"] = {"hit_count": len(vector_memories), "stored": False}
            return AgentRunResponse(
                task_id=task.id,
                status="ok",
                error="",
                content=deterministic,
                model=model,
                model_tier=task.model_tier,
                role_preset=task.role_preset,
                tools_allowed=tools_allowed,
                citations=citations,
                retrieval_trace=retrieval_trace,
                quality_status="ok",
            )

    evidence_text = _build_evidence_prompt_text(citations)
    memory_text = _format_vector_memories(vector_memories, max_items=3)
    task_contract_text = _build_task_contract_instructions(task)
    previous_results_text = json.dumps(previous_results, ensure_ascii=False)
    interpretation_prompt = (
        INTERPRETATION_PROMPT_SOURCES
        if should_use_source_format(task.role_preset)
        else INTERPRETATION_PROMPT_GENERAL
    )
    evidence_policy_line = (
        "Evidence policy: Use ONLY fetched evidence. If insufficient, explicitly say so."
        if retrieval_required
        else (
            "Evidence policy: Use ONLY dependency previous_results and inherited citations. "
            "Do NOT claim lack of fetched evidence when dependency evidence is present."
        )
    )
    prompt = (
        f"User request: {req.user_request}\n"
        f"Refined context: {json.dumps(req.refined, ensure_ascii=False)}\n"
        f"Prompt expert contract version: {prompt_contract.get('contract_version')}\n"
        f"Prompt expert task prompt: {prompt_contract.get('task_prompt')}\n"
        f"Prompt expert constraints: {json.dumps(prompt_contract.get('constraints', []), ensure_ascii=False)}\n"
        f"Task id: {task.id}\n"
        f"Task title: {task.title}\n"
        f"Task description: {task.description or task.goal}\n"
        f"Task goal: {task.goal}\n"
        f"Deliverable: {task.deliverable}\n"
        f"Acceptance: {json.dumps(task.acceptance_criteria, ensure_ascii=False)}\n"
        f"Task suggested_tools: {json.dumps(task.suggested_tools, ensure_ascii=False)}\n"
        f"Task tool_parameters: {json.dumps(task.tool_parameters, ensure_ascii=False)}\n"
        f"{task_contract_text}\n\n"
        f"Dependency previous_results (JSON): {previous_results_text}\n"
        f"Related memories (JSON): {memory_text}\n"
        f"{evidence_policy_line}\n"
        f"{interpretation_prompt}\n\n"
        f"Fetched evidence (JSON): {evidence_text}\n"
    )

    client = OpenAIClient()
    run_timeout = _run_request_timeout(task.model_tier)
    content = client.complete(prompt=prompt, model=model, temperature=0.2, system_prompt=system_prompt, request_timeout=run_timeout)
    is_bad_content = _is_low_value_content(content)
    status = "ok" if content and not _is_model_error_content(content) and not is_bad_content else "error"
    error_message = ""
    if status == "error":
        if _is_model_error_content(content):
            error_message = "model_error"
        elif is_bad_content:
            error_message = "low_relevance_output"
            quality_status = "low_relevance"
        else:
            error_message = "empty_output"

    # 中文注释：结构化输出兜底，优先保证格式可消费
    if _is_structured_task(task) and not _structured_content_valid(task, content):
        fallback_structured = _build_structured_fallback_content(
            task=task,
            previous_results=previous_results,
            citations=citations,
        )
        if fallback_structured:
            content = fallback_structured
            status = "ok"
            error_message = ""
            quality_status = "ok"

    # 中文注释：非转换任务低价值输出降级策略，受 quality_mode 控制
    #   strict  → 保持 error，编排层将触发重试
    #   best_effort → 允许 fallback，但写入 degraded 标记而非伪装为 ok
    if status == "error" and error_message in {"low_relevance_output", "empty_output"} and not _is_transform_only_task(task):
        if req.quality_mode == "strict":
            pass  # 保持 error/error_message 不变，编排层会重试
        else:
            fallback_content = _build_resilient_fallback_content(
                task=task,
                user_request=req.user_request,
                previous_results=previous_results,
                citations=citations,
                retrieval_trace=retrieval_trace,
            )
            content = fallback_content
            status = "ok"
            error_message = ""
            quality_status = "degraded"
            # 中文注释：在 retrieval_trace 中保留降级原因，供编排层感知
            if isinstance(retrieval_trace.get("warnings"), list):
                retrieval_trace["warnings"].append("fallback_degraded")
            else:
                retrieval_trace["warnings"] = ["fallback_degraded"]

    # 中文注释：将本次任务结果写入向量记忆（Qdrant 不可用时自动回退内存）
    if content and status == "ok" and enable_vector_memory:
        try:
            vector_store.upsert_text(
                collection="task_memories",
                text=content,
                payload={
                    "task_id": task.id,
                    "task_title": task.title,
                    "role_preset": task.role_preset,
                    "user_request": req.user_request,
                    "strategy": req.strategy,
                    "citation_count": len(citations),
                },
            )
        except Exception:
            pass

    retrieval_trace["vector_memory"] = {
        "hit_count": len(vector_memories),
        "stored": bool(content and status == "ok" and enable_vector_memory),
    }

    return AgentRunResponse(
        task_id=task.id,
        status=status,
        error=error_message,
        content=content,
        model=model,
        model_tier=task.model_tier,
        role_preset=task.role_preset,
        tools_allowed=tools_allowed,
        citations=citations,
        retrieval_trace=retrieval_trace,
        quality_status=quality_status,
    )


# 中文注释：函数 tool_web_search 的入口
@app.post("/tools/web_search")
def tool_web_search(req: WebSearchRequest):
    return {"results": web_search(query=req.query, max_results=req.max_results, domains=req.domains)}


# 中文注释：函数 tool_url_select 的入口
@app.post("/tools/url_select")
def tool_url_select(req: URLSelectRequest):
    return {"selected": select_candidate_urls(query=req.query, candidates=req.candidates, max_urls=req.max_urls)}


# 中文注释：函数 tool_web_fetch 的入口
@app.post("/tools/web_fetch")
def tool_web_fetch(req: WebFetchRequest):
    return {"pages": web_fetch(urls=req.urls, max_chars=req.max_chars)}


# 中文注释：函数 tool_web_crawl 的入口
@app.post("/tools/web_crawl")
def tool_web_crawl(req: WebCrawlRequest):
    return web_crawl(
        seed_urls=req.seed_urls,
        max_pages_per_seed=req.max_pages_per_seed,
        max_total_pages=req.max_total_pages,
        max_chars=req.max_chars,
    )


# 中文注释：函数 memory_upsert 的入口
@app.post("/memory/upsert")
def memory_upsert(req: MemoryUpsertRequest):
    point_id = vector_store.upsert_text(
        text=req.text,
        payload=req.payload,
        collection=req.collection,
    )
    return {"id": point_id, "collection": req.collection}


# 中文注释：函数 memory_search 的入口
@app.post("/memory/search")
def memory_search(req: MemorySearchRequest):
    hits = vector_store.search_text(
        query=req.query,
        limit=req.limit,
        collection=req.collection,
        filter_payload=req.filter_payload or None,
    )
    return {"collection": req.collection, "hits": hits}


# 中文注释：函数 prompt_expert_generate 的入口
@app.post("/prompt-expert/generate", response_model=PromptExpertResponse)
def prompt_expert_generate(req: PromptExpertRequest) -> PromptExpertResponse:
    contract = build_prompt_contract(
        role_preset=req.role_preset,
        task=req.task,
        user_request=req.user_request,
        refined=req.refined,
    )
    return PromptExpertResponse(**contract)


# 中文注释：函数 tool_execute 的入口（通用工具执行兼容）
@app.post("/v1/tools/execute")
def tool_execute(req: ToolCallRequest):
    return execute_tool_call({"name": req.name, "arguments": req.arguments})
