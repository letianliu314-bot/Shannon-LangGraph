import json

from shannon.llm_service.main import (
    DecomposeRequest,
    TaskContract,
    _compact_refined_for_decompose,
    _complexity_by_strategy,
    _converge_task_dependencies,
    _extract_areas,
    _is_low_value_content,
    _is_model_error_content,
    _normalize_strategy,
    _query_type_by_strategy,
    _validate_decompose_tasks,
    decompose,
)


def test_extract_areas_uses_semantic_clauses():
    query = (
        'Filter using Semantic Scholar (or OpenAlex) with the condition "publication_year = 2025", '
        'then sort by "citationCount/influentialCitationCount", and select the top K. '
        "Extract the abstract of each paper; Based on the abstract, generate N training samples (JSONL), "
        "and each sample must be able to refer back to the paper title + venue + year."
    )

    areas = _extract_areas(query)

    assert areas
    assert areas[:4] != ["Filter", "using", "Semantic", "Scholar"]
    assert any("Semantic Scholar" in area for area in areas)
    assert any("citationCount" in area for area in areas)


def test_extract_areas_preserves_arxiv_ids():
    query = (
        "Search paper LLaMA: Open and Efficient Foundation Language Models arXiv:2302.13971; "
        "then compare with Llama 2 arXiv:2307.09288; "
        "finally compare with Llama 3 arXiv:2407.21783."
    )

    areas = _extract_areas(query)
    joined = " | ".join(areas)
    assert "2302.13971" in joined
    assert "2307.09288" in joined
    assert "2407.21783" in joined


def test_extract_areas_skips_meta_and_transform_constraints():
    query = (
        "Independently research these three papers: (1) DeepSeek LLM, (2) DeepSeek-V2, (3) DeepSeek-V3. "
        "Then synthesize improvements. Generate exactly 10 JSONL samples. "
        "Only synthesis and JSONL generation may depend on upstream tasks. Do not output plans/promises."
    )

    areas = _extract_areas(query)
    joined = " | ".join(areas).lower()
    assert "do not output plans" not in joined
    assert "jsonl" not in joined
    assert "deepseek llm" in joined
    assert "deepseek-v2" in joined
    assert "deepseek-v3" in joined


def test_model_error_content_detection():
    assert _is_model_error_content("[error:gpt-4o] BadRequestError: x")
    assert _is_model_error_content("[fallback:gpt-4o] x")
    assert not _is_model_error_content("[stub:gpt-4o] x")


def test_low_value_content_detection_rejects_plan_language():
    assert _is_low_value_content("I will now fetch more sources and proceed in the next step.")
    assert _is_low_value_content("Would you like me to continue and generate JSONL?")
    assert not _is_low_value_content("The paper reports a 0.5B to 72B model range with dense and MoE variants.")


def test_compact_refined_for_decompose_limits_payload_size():
    refined = {
        "query_type": "deep_research",
        "complexity": "high",
        "normalized_question": "Q" * 800,
        "research_areas": [f"area-{idx}-" + ("x" * 200) for idx in range(1, 8)],
        "extra": "ignored",
    }
    compact = _compact_refined_for_decompose(refined)

    assert compact["query_type"] == "deep_research"
    assert compact["complexity"] == "high"
    assert len(compact["normalized_question"]) == 600
    assert len(compact["research_areas"]) == 4
    assert all(len(area) <= 160 for area in compact["research_areas"])
    assert "extra" not in compact


def test_strategy_mapping_and_fallback():
    assert _normalize_strategy("quick") == "deep"
    assert _normalize_strategy("standard") == "deep"
    assert _normalize_strategy("deep") == "deep"
    assert _normalize_strategy("academic") == "deep"

    assert _query_type_by_strategy("quick") == "deep_research"
    assert _query_type_by_strategy("standard") == "deep_research"
    assert _query_type_by_strategy("deep") == "deep_research"
    assert _query_type_by_strategy("academic") == "deep_research"

    assert _complexity_by_strategy("quick") == "high"
    assert _complexity_by_strategy("standard") == "high"
    assert _complexity_by_strategy("deep") == "high"
    assert _complexity_by_strategy("academic") == "high"


def test_converge_dependencies_collapses_chain_into_parallel_plus_summary():
    tasks = [
        TaskContract(
            id="task-1",
            title="Search paper",
            goal="Search paper sources",
            description="Use web_search to find paper URLs",
            deliverable="narrative",
            tools_allowed=["web_search"],
            suggested_tools=["web_search"],
        ),
        TaskContract(
            id="task-2",
            title="Fetch paper content",
            goal="Fetch content",
            description="Use web_fetch on selected URLs",
            deps=["task-1"],
            deliverable="narrative",
            tools_allowed=["web_fetch"],
            suggested_tools=["web_fetch"],
        ),
        TaskContract(
            id="task-3",
            title="Generate JSONL summary",
            goal="Generate JSONL training data",
            description="Summarize and generate JSONL",
            deps=["task-2"],
            deliverable="structured",
            tools_allowed=[],
            suggested_tools=[],
        ),
    ]

    converged = _converge_task_dependencies(tasks, max_layers=2)
    task_map = {task.id: task for task in converged}

    assert task_map["task-1"].deps == []
    assert task_map["task-2"].deps == []
    assert task_map["task-3"].deps
    assert all(not task_map[dep].deps for dep in task_map["task-3"].deps)


def test_converge_dependencies_enforces_two_layer_dag_depth():
    tasks = [
        TaskContract(
            id="task-1",
            title="Research A",
            goal="Research A",
            description="Research with web_search",
            deliverable="narrative",
            tools_allowed=["web_search"],
            suggested_tools=["web_search"],
        ),
        TaskContract(
            id="task-2",
            title="Research B",
            goal="Research B",
            description="Research with web_fetch",
            deps=["task-1"],
            deliverable="narrative",
            tools_allowed=["web_fetch"],
            suggested_tools=["web_fetch"],
        ),
        TaskContract(
            id="task-3",
            title="Summarize",
            goal="Summarize findings",
            description="Summarize all findings",
            deps=["task-2"],
            deliverable="narrative",
            tools_allowed=[],
            suggested_tools=[],
        ),
        TaskContract(
            id="task-4",
            title="Generate JSONL",
            goal="Generate JSONL",
            description="Generate JSONL from summary",
            deps=["task-3"],
            deliverable="structured",
            tools_allowed=[],
            suggested_tools=[],
        ),
    ]

    converged = _converge_task_dependencies(tasks, max_layers=2)
    task_map = {task.id: task for task in converged}

    # 中文注释：验证 DAG 深度不超过 3 层（research → synthesis → transform）
    # 非转换任务的依赖必须是根层任务（deps=[]）
    # 转换任务允许依赖浅层汇总任务（仅依赖根层的汇总任务）
    def _dag_depth(tid: str, visited: set | None = None) -> int:
        if visited is None:
            visited = set()
        if tid in visited:
            return 0
        visited.add(tid)
        t = task_map.get(tid)
        if t is None or not t.deps:
            return 1
        return 1 + max(_dag_depth(d, visited) for d in t.deps)

    for task in converged:
        depth = _dag_depth(task.id)
        assert depth <= 3, f"{task.id} has depth {depth}, expected <= 3"
        # 非转换/汇总任务不应有依赖（并行采集层）
        for dep in task.deps:
            dep_task = task_map[dep]
            # 每个依赖的依赖只能指向根层任务
            for grandparent in dep_task.deps:
                assert task_map[grandparent].deps == [], (
                    f"{task.id} → {dep} → {grandparent} still has deps {task_map[grandparent].deps}"
                )


def test_decompose_escalates_from_small_to_medium_on_invalid_output(monkeypatch):
    requested_models = []

    def fake_resolve_model(model_tier, model=None):  # noqa: ANN001
        return f"model-{model_tier}"

    class FakeOpenAIClient:
        def complete(self, prompt, model, temperature, system_prompt=None, max_tokens=None, request_timeout=None):  # noqa: ANN001
            requested_models.append(model)
            if model == "model-small":
                return json.dumps(
                    {
                        "subtasks": [
                            {
                                "id": "task-1",
                                "title": "Research all papers",
                                "description": "Research all papers in one task",
                                "dependencies": [],
                                "suggested_tools": ["web_search"],
                            }
                        ]
                    },
                    ensure_ascii=False,
                )
            return json.dumps(
                {
                    "subtasks": [
                        {
                            "id": "task-1",
                            "title": "Research DeepSeek LLM",
                            "description": "Collect evidence for DeepSeek LLM",
                            "dependencies": [],
                            "suggested_tools": ["web_search", "web_fetch"],
                        },
                        {
                            "id": "task-2",
                            "title": "Research DeepSeek-V2",
                            "description": "Collect evidence for DeepSeek-V2",
                            "dependencies": [],
                            "suggested_tools": ["web_search", "web_fetch"],
                        },
                        {
                            "id": "task-merge",
                            "title": "Cross-check findings",
                            "description": "Synthesize improvements",
                            "dependencies": ["task-1", "task-2"],
                            "suggested_tools": [],
                        },
                        {
                            "id": "task-jsonl",
                            "title": "Generate JSONL QA",
                            "description": "Generate JSONL samples",
                            "dependencies": ["task-merge"],
                            "suggested_tools": [],
                            "output_format": {"type": "structured", "required_fields": ["line_id"], "optional_fields": []},
                        },
                    ]
                },
                ensure_ascii=False,
            )

    monkeypatch.setattr("shannon.llm_service.main.resolve_model", fake_resolve_model)
    monkeypatch.setattr("shannon.llm_service.main.OpenAIClient", lambda: FakeOpenAIClient())

    req = DecomposeRequest(
        user_request=(
            "Independently research DeepSeek LLM and DeepSeek-V2, compare improvements, "
            "then generate 10 JSONL QA samples."
        ),
        strategy="deep",
        refined={
            "query_type": "deep_research",
            "research_areas": ["DeepSeek LLM", "DeepSeek-V2", "comparison", "jsonl generation"],
        },
        max_tasks=8,
        role_preset="deep_research_agent",
        model_tier_hint="large",
    )

    resp = decompose(req)
    assert resp.model_tier == "medium"
    assert requested_models[:2] == ["model-small", "model-medium"]
    task_ids = [task.id for task in resp.tasks]
    assert "task-merge" in task_ids
    assert "task-jsonl" in task_ids


def test_decompose_rule_fallback_when_all_tiers_invalid(monkeypatch):
    def fake_resolve_model(model_tier, model=None):  # noqa: ANN001
        return f"model-{model_tier}"

    class FakeOpenAIClient:
        def complete(self, prompt, model, temperature, system_prompt=None, max_tokens=None, request_timeout=None):  # noqa: ANN001
            return "{}"

    monkeypatch.setattr("shannon.llm_service.main.resolve_model", fake_resolve_model)
    monkeypatch.setattr("shannon.llm_service.main.OpenAIClient", lambda: FakeOpenAIClient())

    req = DecomposeRequest(
        user_request=(
            "Independently research three papers and compare (1->2) and (2->3), "
            "then generate exactly 10 JSONL QA training samples."
        ),
        strategy="deep",
        refined={
            "query_type": "deep_research",
            "research_areas": ["paper-1", "paper-2", "paper-3", "comparison and jsonl"],
        },
        max_tasks=8,
        role_preset="deep_research_agent",
        model_tier_hint="large",
    )

    resp = decompose(req)
    task_map = {task.id: task for task in resp.tasks}
    assert resp.model_tier == "large"
    assert "task-merge" in task_map
    assert "task-jsonl" in task_map
    assert task_map["task-jsonl"].deps


def test_validate_decompose_tasks_requires_jsonl_depends_on_merge_for_compare_query():
    tasks = [
        TaskContract(
            id="task-1",
            title="Research DeepSeek LLM",
            goal="Collect evidence for DeepSeek LLM",
            description="Research DeepSeek LLM",
            deliverable="facts_and_citations",
            tools_allowed=["web_search", "web_fetch"],
        ),
        TaskContract(
            id="task-2",
            title="Research DeepSeek-V2",
            goal="Collect evidence for DeepSeek-V2",
            description="Research DeepSeek-V2",
            deliverable="facts_and_citations",
            tools_allowed=["web_search", "web_fetch"],
        ),
        TaskContract(
            id="task-merge",
            title="Cross-check findings",
            goal="Synthesize improvements",
            description="Cross-check",
            deps=["task-1", "task-2"],
            deliverable="conflict_resolution_note",
            tools_allowed=["mcp_fetch"],
        ),
        TaskContract(
            id="task-jsonl",
            title="Generate JSONL QA",
            goal="Generate JSONL",
            description="Generate JSONL samples",
            deps=["task-1"],
            deliverable="structured_jsonl",
            output_format={
                "type": "structured",
                "required_fields": ["line_id", "question", "answer", "source", "difficulty"],
                "optional_fields": [],
            },
            tools_allowed=["mcp_fetch"],
        ),
    ]

    invalid, reasons = _validate_decompose_tasks(
        tasks,
        "Compare DeepSeek LLM and DeepSeek-V2, then generate 10 JSONL samples.",
    )
    assert invalid is True
    assert "jsonl_not_dependent_on_merge" in reasons
