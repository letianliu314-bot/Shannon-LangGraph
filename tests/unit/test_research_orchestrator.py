from shannon.orchestration.orchestrator.graph import (
    _build_task_graph,
    _downgrade_dependencies_for_parallel,
    decompose_node,
    determine_model_tier,
    finalize_node,
    schedule_node,
)

# 中文注释：研究编排策略测试


def test_determine_model_tier_policy():
    # 中文注释：quick/standard/deep 分别对应 small/medium/large，非法值回退 deep；decompose/finalize 固定档位
    assert determine_model_tier("quick", "planning") == "small"
    assert determine_model_tier("standard", "planning") == "medium"
    assert determine_model_tier("deep", "planning") == "large"
    assert determine_model_tier("academic", "planning") == "large"
    assert determine_model_tier("quick", "decompose") == "small"
    assert determine_model_tier("quick", "finalize") == "large"


def test_build_task_graph_missing_dependency():
    # 中文注释：缺失依赖会记录错误并忽略无效依赖
    tasks = [
        {"id": "t1", "goal": "a", "deps": []},
        {"id": "t2", "goal": "b", "deps": ["not_exist"]},
    ]
    task_map, dependency_count, reverse_dependencies, ready_queue, errors = _build_task_graph(tasks)

    assert set(task_map.keys()) == {"t1", "t2"}
    assert dependency_count["t1"] == 0
    assert dependency_count["t2"] == 0
    assert set(ready_queue) == {"t1", "t2"}
    assert reverse_dependencies["t1"] == []
    assert any(item.get("type") == "missing_dependency" for item in errors)


def test_parallel_downgrade_produces_multiple_ready_tasks_for_concurrency():
    tasks = [
        {"id": "task-1", "goal": "search", "deps": []},
        {"id": "task-2", "goal": "select", "deps": ["task-1"]},
        {"id": "task-3", "goal": "fetch", "deps": ["task-2"]},
    ]
    task_map, _, _, ready_queue, _ = _build_task_graph(tasks)
    assert ready_queue == ["task-1"]

    downgraded_map, _, _, downgraded_ready, _, dropped_edges = _downgrade_dependencies_for_parallel(task_map)
    assert dropped_edges == 2
    assert len(downgraded_ready) >= 2

    scheduled = schedule_node(
        {
            "ready_queue": downgraded_ready,
            "task_map": downgraded_map,
            "max_concurrency": 2,
        }
    )
    assert len(scheduled["active_task_ids"]) == 2


def test_decompose_node_timeout_falls_back_to_local_plan(monkeypatch):
    class TimeoutLLMServiceClient:
        def __init__(self, base_url, timeout=60.0, max_retries=0):  # noqa: D401, ANN001
            self.base_url = base_url
            self.timeout = timeout
            self.max_retries = max_retries

        def decompose(
            self,
            user_request,
            strategy,
            refined,
            max_tasks,
            role_preset,
            model_tier_hint=None,
            timeout=None,
            max_retries=None,
        ):  # noqa: ANN001
            raise RuntimeError("timed out")

    monkeypatch.setattr(
        "shannon.orchestration.orchestrator.graph.LLMServiceClient",
        TimeoutLLMServiceClient,
    )

    state = {
        "thread_id": "t-timeout",
        "user_request": "Research topic A and topic B",
        "strategy": "deep",
        "refined": {
            "query_type": "deep_research",
            "research_areas": ["topic A", "topic B"],
            "complexity": "high",
        },
        "max_tasks": 6,
        "llm_service_base_url": "http://127.0.0.1:8001",
        "errors": [],
    }

    out = decompose_node(state)
    assert out["done"] is False
    assert out["task_map"]
    assert len(out["ready_queue"]) >= 1
    assert any(item.get("type") == "decompose_fallback" for item in out["errors"])


def test_decompose_node_retry_uses_compact_request_and_avoids_fallback(monkeypatch):
    class RetryLLMServiceClient:
        call_count = 0

        def __init__(self, base_url, timeout=60.0, max_retries=0):  # noqa: D401, ANN001
            self.base_url = base_url
            self.timeout = timeout
            self.max_retries = max_retries

        def decompose(
            self,
            user_request,
            strategy,
            refined,
            max_tasks,
            role_preset,
            model_tier_hint=None,
            timeout=None,
            max_retries=None,
        ):  # noqa: ANN001
            RetryLLMServiceClient.call_count += 1
            if RetryLLMServiceClient.call_count == 1:
                raise RuntimeError("timed out")
            assert max_tasks <= 4
            assert "normalized_question" in refined
            return {
                "tasks": [
                    {
                        "id": "task-1",
                        "goal": "Collect evidence",
                        "description": "Collect evidence",
                        "deps": [],
                    },
                    {
                        "id": "task-2",
                        "goal": "Summarize",
                        "description": "Summarize findings",
                        "deps": ["task-1"],
                    },
                ]
            }

    monkeypatch.setattr(
        "shannon.orchestration.orchestrator.graph.LLMServiceClient",
        RetryLLMServiceClient,
    )

    state = {
        "thread_id": "t-retry",
        "user_request": "Research topic A and summarize",
        "strategy": "deep",
        "refined": {
            "query_type": "deep_research",
            "normalized_question": "Research topic A and summarize",
            "research_areas": ["topic A", "summary"],
            "complexity": "high",
        },
        "max_tasks": 8,
        "llm_service_base_url": "http://127.0.0.1:8001",
        "errors": [],
    }

    out = decompose_node(state)
    assert out["done"] is False
    assert out["task_map"]
    assert not any(item.get("type") == "decompose_fallback" for item in out["errors"])


def test_decompose_fallback_ignores_fragmented_refined_areas(monkeypatch):
    class TimeoutLLMServiceClient:
        def __init__(self, base_url, timeout=60.0, max_retries=0):  # noqa: D401, ANN001
            self.base_url = base_url
            self.timeout = timeout
            self.max_retries = max_retries

        def decompose(
            self,
            user_request,
            strategy,
            refined,
            max_tasks,
            role_preset,
            model_tier_hint=None,
            timeout=None,
            max_retries=None,
        ):  # noqa: ANN001
            raise RuntimeError("timed out")

    monkeypatch.setattr(
        "shannon.orchestration.orchestrator.graph.LLMServiceClient",
        TimeoutLLMServiceClient,
    )

    state = {
        "thread_id": "t-fallback-areas",
        "user_request": (
            "Compare LLaMA arXiv:2302.13971 with Llama 2 arXiv:2307.09288 and "
            "Llama 3 arXiv:2407.21783, then produce JSONL."
        ),
        "strategy": "deep",
        "refined": {
            "query_type": "deep_research",
            "research_areas": ["arXiv (line 2302)", "line 2307", "line 2407"],
            "complexity": "high",
        },
        "max_tasks": 6,
        "llm_service_base_url": "http://127.0.0.1:8001",
        "errors": [],
    }

    out = decompose_node(state)
    task_titles = [task.get("title", "") for task in out["tasks"]]
    joined = " | ".join(task_titles)
    assert "line 2302" not in joined.lower()
    assert "2302.13971" in joined


def test_decompose_fallback_builds_parallel_merge_and_jsonl(monkeypatch):
    class TimeoutLLMServiceClient:
        def __init__(self, base_url, timeout=60.0, max_retries=0):  # noqa: D401, ANN001
            self.base_url = base_url
            self.timeout = timeout
            self.max_retries = max_retries

        def decompose(
            self,
            user_request,
            strategy,
            refined,
            max_tasks,
            role_preset,
            model_tier_hint=None,
            timeout=None,
            max_retries=None,
        ):  # noqa: ANN001
            raise RuntimeError("timed out")

    monkeypatch.setattr(
        "shannon.orchestration.orchestrator.graph.LLMServiceClient",
        TimeoutLLMServiceClient,
    )

    state = {
        "thread_id": "t-fallback-jsonl",
        "user_request": (
            "Compare LLaMA 1 arXiv:2302.13971, Llama 2 arXiv:2307.09288, and "
            "Llama 3 arXiv:2407.21783, then generate 10 JSONL QA samples about improvements."
        ),
        "strategy": "deep",
        "refined": {
            "query_type": "deep_research",
            "research_areas": [
                "LLaMA 1 arXiv:2302.13971",
                "Llama 2 arXiv:2307.09288",
                "Llama 3 arXiv:2407.21783",
            ],
            "complexity": "high",
        },
        "max_tasks": 8,
        "llm_service_base_url": "http://127.0.0.1:8001",
        "errors": [],
    }

    out = decompose_node(state)
    tasks = out["tasks"]
    task_by_id = {task["id"]: task for task in tasks}

    assert "task-merge" in task_by_id
    assert "task-jsonl" in task_by_id

    research_ids = [task["id"] for task in tasks if task["id"].startswith("task-") and task["id"][5:].isdigit()]
    assert len(research_ids) >= 2
    assert all(task_by_id[task_id]["deps"] == [] for task_id in research_ids)
    assert set(task_by_id["task-merge"]["deps"]) == set(research_ids)
    assert task_by_id["task-jsonl"]["deps"] == ["task-merge"]
    assert len(out["ready_queue"]) >= 2


def test_decompose_fallback_filters_meta_and_transform_areas(monkeypatch):
    class TimeoutLLMServiceClient:
        def __init__(self, base_url, timeout=60.0, max_retries=0):  # noqa: D401, ANN001
            self.base_url = base_url
            self.timeout = timeout
            self.max_retries = max_retries

        def decompose(
            self,
            user_request,
            strategy,
            refined,
            max_tasks,
            role_preset,
            model_tier_hint=None,
            timeout=None,
            max_retries=None,
        ):  # noqa: ANN001
            raise RuntimeError("timed out")

    monkeypatch.setattr(
        "shannon.orchestration.orchestrator.graph.LLMServiceClient",
        TimeoutLLMServiceClient,
    )

    state = {
        "thread_id": "t-fallback-filtering",
        "user_request": (
            "Independently research these three papers: (1) DeepSeek LLM, (2) DeepSeek-V2, (3) DeepSeek-V3. "
            "Then synthesize improvements and generate exactly 10 JSONL samples. "
            "Only synthesis and JSONL generation may depend on upstream tasks. Do not output plans/promises."
        ),
        "strategy": "deep",
        "refined": {
            "query_type": "deep_research",
            "research_areas": [
                "Independently research these three papers: (1) DeepSeek LLM, (2) DeepSeek-V2, (3) DeepSeek-V3",
                "synthesize the improvements from (1->2) and (2->3)",
                "generate exactly 10 JSONL Q&A training samples",
                "only synthesis and JSONL generation may depend on upstream tasks. Do not output plans/promises",
            ],
            "complexity": "high",
        },
        "max_tasks": 8,
        "llm_service_base_url": "http://127.0.0.1:8001",
        "errors": [],
    }

    out = decompose_node(state)
    tasks = out["tasks"]
    research_titles = " | ".join(
        task["title"] for task in tasks if task["id"].startswith("task-") and task["id"][5:].isdigit()
    ).lower()
    assert "jsonl" not in research_titles
    assert "synthesize" not in research_titles
    assert "do not output plans" not in research_titles


def test_finalize_timeout_records_error(monkeypatch):
    class TimeoutLLMServiceClient:
        def __init__(self, base_url, timeout=60.0, max_retries=0):  # noqa: D401, ANN001
            self.base_url = base_url
            self.timeout = timeout
            self.max_retries = max_retries

        def respond(self, prompt, model_tier, system_prompt=None, timeout=None, max_retries=None):  # noqa: ANN001
            raise RuntimeError("timed out")

    monkeypatch.setattr(
        "shannon.orchestration.orchestrator.graph.LLMServiceClient",
        TimeoutLLMServiceClient,
    )

    state = {
        "thread_id": "t-finalize-timeout",
        "user_request": "Summarize findings",
        "strategy": "deep",
        "refined": {"query_type": "deep_research"},
        "task_map": {
            "task-1": {"id": "task-1", "title": "Task 1", "goal": "Goal 1", "status": "succeeded"},
        },
        "task_results": {
            "task-1": {"task_id": "task-1", "status": "ok", "content": "content-1"},
        },
        "errors": [],
        "budget": {"max_token": 1000, "used_token": 10, "max_retry": 2},
    }

    out = finalize_node(state)
    assert out["done"] is True
    assert out["final_output"]["summary"].startswith("[finalize-fallback]")
    assert any(item.get("type") == "finalize_failed" for item in out["final_output"]["errors"])
