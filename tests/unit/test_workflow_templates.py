from shannon.orchestration.workflows.loader import (
    compile_workflow_template,
    load_workflow_template,
)


def _node_map(template: dict) -> dict:
    return {str(node["id"]): node for node in template.get("nodes", [])}


def _task_map(compiled: dict) -> dict:
    return {str(task["id"]): task for task in compiled.get("tasks", [])}


def test_template_extends_merge() -> None:
    template = load_workflow_template("market_analysis_playbook")
    nodes = _node_map(template)

    assert template["name"] == "market_analysis_playbook"
    assert "understand" in nodes
    assert "competitors_dag" in nodes
    assert "compliance_review" in nodes
    assert nodes["report"]["metadata"]["report_template"] == "playbook_v1"


def test_compile_dag_tasks() -> None:
    template = load_workflow_template("parallel_dag_example")
    compiled = compile_workflow_template(template, user_request="Analyze a market")
    tasks = _task_map(compiled)

    assert "parallel_analysis::data_collection" in tasks
    assert "parallel_analysis::quantitative_analysis" in tasks
    assert "parallel_analysis::qualitative_analysis" in tasks
    assert "parallel_analysis::cross_validation" in tasks
    assert tasks["parallel_analysis"]["deps"] == ["parallel_analysis::cross_validation"]
    assert tasks["report"]["deps"] == ["parallel_analysis"]


def test_compile_parallel_by_tasks() -> None:
    template = load_workflow_template("parallel_items_example")
    compiled = compile_workflow_template(
        template,
        user_request="Build weekly digest",
        context={"topics": ["AI", "Cybersecurity"], "depth": "brief"},
    )
    tasks = _task_map(compiled)

    assert "research_topics::1" in tasks
    assert "research_topics::2" in tasks
    assert tasks["research_topics"]["deps"] == ["research_topics::1", "research_topics::2"]
    assert tasks["synthesize_report"]["deps"] == ["research_topics"]
