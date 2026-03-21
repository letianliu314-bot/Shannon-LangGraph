# Shared Memory Layer Layout (Phase 1)

本规范定义单分支仓库下 run 目录隔离与命名规则。

## Root

- Root path: `reports/`
- Run path: `reports/<run_id>/`
- `<run_id>` 仅允许字符集 `[a-zA-Z0-9_.-]`，其他字符会被标准化为 `-`。

## Required Files

- `reports/<run_id>/run_manifest.json`
  - 记录运行策略、阶段、创建时间
- `reports/<run_id>/memory_index.jsonl`
  - 每行一个任务产物索引记录（append-only）

## Task Artifact Paths

- Draft: `reports/<run_id>/<agent>/<task_id>/draft.md`
- Final: `reports/<run_id>/<agent>/<task_id>/final.md`
- Metadata: `reports/<run_id>/<agent>/<task_id>/meta.json`

命名规则：
- `<agent>` 与 `<task_id>` 采用与 run_id 相同的字符标准化规则
- 禁止绝对路径写入
- 禁止 `..` 路径穿越

## Search Contract

检索过滤字段：
- `run_id`
- `task_id`
- `stage`
- `capability`
- `limit`

返回字段：
- `run_id`
- `task_id`
- `stage`
- `capability`
- `agent`
- `artifact_path`
- `artifact_name`
- `timestamp`
- `content`
- `metadata` (optional)

## Fallback Rule

编排层读取 previous_results 时：
1. 优先从共享记忆层按依赖 task_id 检索
2. 未命中时回退到依赖透传
3. 回退时发布 `SHARED_MEMORY_DEGRADED` 事件
