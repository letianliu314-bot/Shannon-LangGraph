from __future__ import annotations

import copy
import os
from collections import deque
from pathlib import Path
from typing import Any, Deque, Dict, Iterable, List, Sequence, Set, Tuple

import yaml


class WorkflowTemplateError(ValueError):
    pass


def _repo_root() -> Path:
    return Path(__file__).resolve().parents[4]


def _default_template_dirs() -> List[Path]:
    env_value = os.getenv("WORKFLOW_TEMPLATE_PATHS") or os.getenv("TEMPLATES_PATH")
    if env_value:
        dirs = [Path(item).expanduser() for item in env_value.split(":") if item.strip()]
        return [item.resolve() for item in dirs if item.exists()]

    base = _repo_root() / "config" / "workflows"
    candidates = [base / "examples", base / "user", base]
    return [item.resolve() for item in candidates if item.exists()]


def _normalize_template_dirs(template_dirs: Sequence[str | Path] | None) -> List[Path]:
    if template_dirs is None:
        return _default_template_dirs()
    normalized = [Path(item).expanduser().resolve() for item in template_dirs]
    return [item for item in normalized if item.exists()]


def _read_yaml(path: Path) -> Dict[str, Any]:
    try:
        data = yaml.safe_load(path.read_text(encoding="utf-8"))
    except Exception as exc:  # noqa: BLE001
        raise WorkflowTemplateError(f"failed to parse template YAML: {path}, error={exc}") from exc

    if not isinstance(data, dict):
        raise WorkflowTemplateError(f"template must be an object: {path}")
    return data


def _resolve_template_path(
    template_ref: str,
    template_dirs: Sequence[Path],
    current_dir: Path | None = None,
) -> Path:
    reference = Path(template_ref).expanduser()

    # Explicit path
    if reference.is_absolute() or "/" in template_ref or "\\" in template_ref or template_ref.startswith("."):
        if current_dir is not None and not reference.is_absolute():
            candidate = (current_dir / reference).resolve()
            if candidate.exists():
                return candidate
        resolved = reference.resolve()
        if resolved.exists():
            return resolved
        raise WorkflowTemplateError(f"template path not found: {template_ref}")

    # Name lookup
    names = [template_ref]
    if not template_ref.endswith((".yaml", ".yml")):
        names.extend([f"{template_ref}.yaml", f"{template_ref}.yml"])

    for directory in template_dirs:
        for name in names:
            candidate = (directory / name).resolve()
            if candidate.exists():
                return candidate
    raise WorkflowTemplateError(f"template not found: {template_ref}")


def _deep_merge_dict(base: Dict[str, Any], override: Dict[str, Any]) -> Dict[str, Any]:
    merged = copy.deepcopy(base)
    for key, value in override.items():
        if isinstance(value, dict) and isinstance(merged.get(key), dict):
            merged[key] = _deep_merge_dict(merged[key], value)
        else:
            merged[key] = copy.deepcopy(value)
    return merged


def _merge_nodes(base_nodes: List[Dict[str, Any]], override_nodes: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    merged: List[Dict[str, Any]] = [copy.deepcopy(item) for item in base_nodes]
    by_id: Dict[str, int] = {}
    for index, item in enumerate(merged):
        node_id = str(item.get("id") or "")
        if node_id:
            by_id[node_id] = index

    for node in override_nodes:
        node_id = str(node.get("id") or "")
        if not node_id:
            merged.append(copy.deepcopy(node))
            continue

        if node_id not in by_id:
            by_id[node_id] = len(merged)
            merged.append(copy.deepcopy(node))
            continue

        index = by_id[node_id]
        base = merged[index]
        if isinstance(base, dict) and isinstance(node, dict):
            merged[index] = _deep_merge_dict(base, node)
        else:
            merged[index] = copy.deepcopy(node)
    return merged


def _merge_template_dicts(base: Dict[str, Any], override: Dict[str, Any]) -> Dict[str, Any]:
    merged = copy.deepcopy(base)
    for key, value in override.items():
        if key == "extends":
            continue
        if key in {"defaults", "metadata"} and isinstance(value, dict):
            merged[key] = _deep_merge_dict(dict(merged.get(key, {})), value)
            continue
        if key == "nodes" and isinstance(value, list):
            merged[key] = _merge_nodes(list(merged.get("nodes", [])), value)
            continue
        if key == "edges" and isinstance(value, list):
            merged[key] = copy.deepcopy(value)
            continue
        merged[key] = copy.deepcopy(value)
    return merged


def _validate_required_fields(template: Dict[str, Any]) -> None:
    if not str(template.get("name") or "").strip():
        raise WorkflowTemplateError("template field 'name' is required")
    nodes = template.get("nodes")
    if not isinstance(nodes, list) or not nodes:
        raise WorkflowTemplateError("template field 'nodes' must be a non-empty list")


def _normalize_node_dependencies(template: Dict[str, Any]) -> Dict[str, Set[str]]:
    nodes = template.get("nodes", [])
    node_ids: Set[str] = set()
    dependency_map: Dict[str, Set[str]] = {}

    for node in nodes:
        if not isinstance(node, dict):
            raise WorkflowTemplateError("each node must be an object")
        node_id = str(node.get("id") or "").strip()
        if not node_id:
            raise WorkflowTemplateError("each node must have a non-empty id")
        if node_id in node_ids:
            raise WorkflowTemplateError(f"duplicate node id: {node_id}")
        node_ids.add(node_id)

        depends_on = node.get("depends_on", [])
        if depends_on is None:
            depends_on = []
        if not isinstance(depends_on, list):
            raise WorkflowTemplateError(f"node '{node_id}' depends_on must be a list")
        dependency_map[node_id] = {str(dep).strip() for dep in depends_on if str(dep).strip()}

    edges = template.get("edges", [])
    if edges is None:
        edges = []
    if not isinstance(edges, list):
        raise WorkflowTemplateError("template field 'edges' must be a list")

    for edge in edges:
        if not isinstance(edge, dict):
            raise WorkflowTemplateError("edge must be an object")
        source = str(edge.get("from") or "").strip()
        target = str(edge.get("to") or "").strip()
        if not source or not target:
            raise WorkflowTemplateError("edge must contain both 'from' and 'to'")
        if source not in node_ids or target not in node_ids:
            raise WorkflowTemplateError(f"edge references unknown node: {source} -> {target}")
        dependency_map[target].add(source)

    for node_id, deps in dependency_map.items():
        unknown = [item for item in deps if item not in node_ids]
        if unknown:
            raise WorkflowTemplateError(f"node '{node_id}' has unknown dependencies: {unknown}")
        if node_id in deps:
            raise WorkflowTemplateError(f"node '{node_id}' depends on itself")
    return dependency_map


def _topological_order(dependency_map: Dict[str, Set[str]]) -> List[str]:
    reverse_map: Dict[str, Set[str]] = {node_id: set() for node_id in dependency_map}
    indegree: Dict[str, int] = {node_id: len(deps) for node_id, deps in dependency_map.items()}

    for node_id, deps in dependency_map.items():
        for dep in deps:
            reverse_map.setdefault(dep, set()).add(node_id)

    queue: Deque[str] = deque(sorted(node_id for node_id, degree in indegree.items() if degree == 0))
    ordered: List[str] = []

    while queue:
        node_id = queue.popleft()
        ordered.append(node_id)
        for child in sorted(reverse_map.get(node_id, set())):
            indegree[child] -= 1
            if indegree[child] == 0:
                queue.append(child)

    if len(ordered) != len(dependency_map):
        pending = sorted(node_id for node_id in dependency_map if node_id not in ordered)
        raise WorkflowTemplateError(f"template contains cycle(s), unresolved nodes: {pending}")
    return ordered


def _resolve_extends_field(value: Any) -> List[str]:
    if value is None:
        return []
    if isinstance(value, list):
        return [str(item).strip() for item in value if str(item).strip()]
    if isinstance(value, str) and value.strip():
        return [value.strip()]
    raise WorkflowTemplateError("template field 'extends' must be a string or list of strings")


def _load_template_recursive(
    path: Path,
    template_dirs: Sequence[Path],
    stack: List[Path],
    cache: Dict[Path, Dict[str, Any]],
) -> Dict[str, Any]:
    normalized_path = path.resolve()
    if normalized_path in stack:
        chain = " -> ".join(item.name for item in stack + [normalized_path])
        raise WorkflowTemplateError(f"template extends cycle detected: {chain}")

    if normalized_path in cache:
        return copy.deepcopy(cache[normalized_path])

    raw = _read_yaml(normalized_path)
    parents = _resolve_extends_field(raw.get("extends"))

    merged: Dict[str, Any] = {}
    stack.append(normalized_path)
    try:
        for parent_ref in parents:
            parent_path = _resolve_template_path(
                parent_ref,
                template_dirs=template_dirs,
                current_dir=normalized_path.parent,
            )
            parent_template = _load_template_recursive(parent_path, template_dirs, stack, cache)
            merged = _merge_template_dicts(merged, parent_template)
    finally:
        stack.pop()

    merged = _merge_template_dicts(merged, raw)
    merged.setdefault("name", normalized_path.stem)
    merged["_template_path"] = str(normalized_path)
    cache[normalized_path] = copy.deepcopy(merged)
    return merged


def load_workflow_template(
    template_ref: str,
    template_dirs: Sequence[str | Path] | None = None,
) -> Dict[str, Any]:
    dirs = _normalize_template_dirs(template_dirs)
    path = _resolve_template_path(template_ref, dirs)
    template = _load_template_recursive(path, template_dirs=dirs, stack=[], cache={})
    _validate_required_fields(template)
    dependency_map = _normalize_node_dependencies(template)
    _topological_order(dependency_map)
    return template


def list_workflow_templates(template_dirs: Sequence[str | Path] | None = None) -> List[Dict[str, Any]]:
    dirs = _normalize_template_dirs(template_dirs)
    discovered: Dict[str, Dict[str, Any]] = {}

    for directory in dirs:
        for path in sorted(directory.rglob("*.yaml")) + sorted(directory.rglob("*.yml")):
            try:
                raw = _read_yaml(path)
            except WorkflowTemplateError:
                continue

            name = str(raw.get("name") or path.stem)
            if name in discovered:
                continue
            discovered[name] = {
                "name": name,
                "version": str(raw.get("version") or ""),
                "description": str(raw.get("description") or ""),
                "path": str(path.resolve()),
            }

    return [discovered[key] for key in sorted(discovered)]


def _as_string_list(value: Any) -> List[str]:
    if not isinstance(value, list):
        return []
    return [str(item) for item in value if str(item).strip()]


def _safe_prompt_render(template: str, item: str, index: int, context: Dict[str, Any]) -> str:
    payload = dict(context)
    payload["item"] = item
    payload["index"] = index
    try:
        return template.format(**payload)
    except Exception:  # noqa: BLE001
        return f"{template}\n\nitem={item}"


def _build_task_contract(
    task_id: str,
    title: str,
    goal: str,
    deps: Iterable[str],
    model_tier: str,
    tools_allowed: List[str],
    role_preset: str,
    deliverable: str,
) -> Dict[str, Any]:
    return {
        "id": task_id,
        "title": title,
        "goal": goal,
        "deps": list(dict.fromkeys(str(item) for item in deps if str(item).strip())),
        "deliverable": deliverable,
        "acceptance_criteria": ["produce a concise and evidence-backed output"],
        "model_tier": model_tier,
        "role_preset": role_preset,
        "tools_allowed": tools_allowed,
        "status": "pending",
        "retry_count": 0,
    }


def _compile_dag_internal_tasks(
    node: Dict[str, Any],
    external_deps: List[str],
    defaults: Dict[str, Any],
) -> Tuple[List[Dict[str, Any]], List[str]]:
    metadata = node.get("metadata", {}) if isinstance(node.get("metadata"), dict) else {}
    dag_tasks = metadata.get("tasks")
    if not isinstance(dag_tasks, list) or not dag_tasks:
        return [], []

    internal_ids: Set[str] = set()
    internal_deps: Dict[str, Set[str]] = {}
    for item in dag_tasks:
        if not isinstance(item, dict):
            raise WorkflowTemplateError(f"node '{node.get('id')}' metadata.tasks contains non-object entry")
        task_id = str(item.get("id") or "").strip()
        if not task_id:
            raise WorkflowTemplateError(f"node '{node.get('id')}' metadata.tasks item is missing id")
        if task_id in internal_ids:
            raise WorkflowTemplateError(f"node '{node.get('id')}' metadata.tasks has duplicate id: {task_id}")
        internal_ids.add(task_id)
        depends = _as_string_list(item.get("depends_on"))
        internal_deps[task_id] = {dep for dep in depends if dep}

    for task_id, deps in internal_deps.items():
        unknown = [dep for dep in deps if dep not in internal_ids]
        if unknown:
            raise WorkflowTemplateError(
                f"node '{node.get('id')}' metadata.tasks item '{task_id}' references unknown depends_on: {unknown}"
            )
        if task_id in deps:
            raise WorkflowTemplateError(
                f"node '{node.get('id')}' metadata.tasks item '{task_id}' depends on itself"
            )

    _topological_order(internal_deps)
    model_tier = str(node.get("model_tier") or defaults.get("model_tier") or "medium")
    role_preset = str(node.get("role_preset") or "deep_research_agent")
    node_tools = _as_string_list(node.get("tools_allowlist"))

    contracts: List[Dict[str, Any]] = []
    prefixed_ids: Dict[str, str] = {
        task_id: f"{str(node.get('id'))}::{task_id}"
        for task_id in internal_deps
    }
    for item in dag_tasks:
        task_id = str(item.get("id"))
        prefixed_id = prefixed_ids[task_id]
        raw_deps = internal_deps[task_id]
        deps = [prefixed_ids[dep] for dep in raw_deps]
        if not deps:
            deps = list(external_deps)

        query = str(item.get("query") or f"Execute DAG sub-task {task_id}")
        tools_allowed = _as_string_list(item.get("tools")) or list(node_tools)
        contracts.append(
            _build_task_contract(
                task_id=prefixed_id,
                title=f"{node.get('id')}::{task_id}",
                goal=query,
                deps=deps,
                model_tier=model_tier,
                tools_allowed=tools_allowed,
                role_preset=role_preset,
                deliverable=f"sub-result of {node.get('id')}",
            )
        )

    depended: Set[str] = set()
    for deps in internal_deps.values():
        depended.update(deps)
    leaves = [task_id for task_id in internal_deps if task_id not in depended]
    aggregator_deps = [prefixed_ids[item] for item in leaves]
    return contracts, aggregator_deps


def _compile_parallel_by_tasks(
    node: Dict[str, Any],
    external_deps: List[str],
    defaults: Dict[str, Any],
    context: Dict[str, Any],
) -> Tuple[List[Dict[str, Any]], List[str]]:
    metadata = node.get("metadata", {}) if isinstance(node.get("metadata"), dict) else {}
    parallel_by = str(metadata.get("parallel_by") or "").strip()
    if not parallel_by:
        return [], []

    items = context.get(parallel_by)
    if not isinstance(items, list) or not items:
        return [], []

    model_tier = str(node.get("model_tier") or defaults.get("model_tier") or "medium")
    role_preset = str(node.get("role_preset") or "deep_research_agent")
    tools_allowed = _as_string_list(node.get("tools_allowlist"))
    prompt_template = str(metadata.get("prompt_template") or "")

    contracts: List[Dict[str, Any]] = []
    parallel_ids: List[str] = []
    for index, item in enumerate(items, start=1):
        parallel_id = f"{str(node.get('id'))}::{index}"
        parallel_ids.append(parallel_id)
        item_label = str(item)
        goal = (
            _safe_prompt_render(prompt_template, item_label, index, context)
            if prompt_template
            else f"Process item: {item_label}"
        )
        contracts.append(
            _build_task_contract(
                task_id=parallel_id,
                title=f"{node.get('id')}::{item_label}",
                goal=goal,
                deps=external_deps,
                model_tier=model_tier,
                tools_allowed=list(tools_allowed),
                role_preset=role_preset,
                deliverable=f"result for {item_label}",
            )
        )
    return contracts, parallel_ids


def compile_workflow_template(
    template: Dict[str, Any],
    user_request: str,
    context: Dict[str, Any] | None = None,
) -> Dict[str, Any]:
    _validate_required_fields(template)
    dependency_map = _normalize_node_dependencies(template)
    node_order = _topological_order(dependency_map)

    context = dict(context or {})
    defaults = template.get("defaults", {}) if isinstance(template.get("defaults"), dict) else {}
    nodes = template.get("nodes", [])
    node_map: Dict[str, Dict[str, Any]] = {str(node.get("id")): node for node in nodes if isinstance(node, dict)}

    contracts: List[Dict[str, Any]] = []
    for node_id in node_order:
        node = node_map[node_id]
        external_deps = sorted(dependency_map.get(node_id, set()))
        node_type = str(node.get("type") or "simple")
        strategy = str(node.get("strategy") or "react")
        model_tier = str(node.get("model_tier") or defaults.get("model_tier") or "medium")
        role_preset = str(node.get("role_preset") or "deep_research_agent")
        tools_allowed = _as_string_list(node.get("tools_allowlist"))

        dag_subtasks, dag_aggregator_deps = _compile_dag_internal_tasks(
            node=node,
            external_deps=external_deps,
            defaults=defaults,
        )
        contracts.extend(dag_subtasks)

        parallel_subtasks, parallel_aggregator_deps = _compile_parallel_by_tasks(
            node=node,
            external_deps=external_deps,
            defaults=defaults,
            context=context,
        )
        contracts.extend(parallel_subtasks)

        aggregator_deps: List[str] = []
        if dag_aggregator_deps:
            aggregator_deps.extend(dag_aggregator_deps)
        if parallel_aggregator_deps:
            aggregator_deps.extend(parallel_aggregator_deps)
        if not aggregator_deps:
            aggregator_deps = external_deps

        metadata = node.get("metadata", {}) if isinstance(node.get("metadata"), dict) else {}
        metadata_query = str(metadata.get("query") or "").strip()
        description = str(metadata.get("description") or "").strip()

        goal_parts = [
            f"Workflow `{template.get('name')}` node `{node_id}`",
            f"type={node_type}",
            f"strategy={strategy}",
        ]
        if metadata_query:
            goal_parts.append(f"query={metadata_query}")
        elif description:
            goal_parts.append(f"description={description}")
        else:
            goal_parts.append(f"user_request={user_request}")

        contracts.append(
            _build_task_contract(
                task_id=node_id,
                title=str(node.get("title") or node_id),
                goal=" | ".join(goal_parts),
                deps=aggregator_deps,
                model_tier=model_tier,
                tools_allowed=tools_allowed,
                role_preset=role_preset,
                deliverable=f"output of workflow node {node_id}",
            )
        )

    task_ids = {str(item.get("id")) for item in contracts}
    for task in contracts:
        for dep in task.get("deps", []):
            if dep not in task_ids:
                raise WorkflowTemplateError(
                    f"compiled task '{task.get('id')}' depends on unknown task '{dep}'"
                )

    budget_per_node = int(defaults.get("budget_agent_max", 2000) or 2000)
    max_retry = 2
    for node in template.get("nodes", []):
        if not isinstance(node, dict):
            continue
        on_fail = node.get("on_fail")
        if not isinstance(on_fail, dict):
            continue
        retry = on_fail.get("retry")
        if isinstance(retry, int):
            max_retry = max(max_retry, retry)

    return {
        "name": str(template.get("name")),
        "description": str(template.get("description") or ""),
        "template_path": str(template.get("_template_path") or ""),
        "tasks": contracts,
        "budget": {
            "max_token": max(16000, budget_per_node * max(1, len(contracts))),
            "used_token": 0,
            "max_retry": max_retry,
        },
    }
