# Shannon 后端 — 修改历史记录

> 最后更新：2026-03-08 (补充前端实时 Graph + 工具链修复)  
> 按日期记录后端（编排层 / LLM 服务 / 基础设施）的所有修改

---

## 目录

- [Shannon 后端 — 修改历史记录](#shannon-后端--修改历史记录)
  - [目录](#目录)
  - [2026-03-04：首次部署调试 \& 生产修复](#2026-03-04首次部署调试--生产修复)
    - [1. PostgreSQL 持久化降级修复](#1-postgresql-持久化降级修复)
    - [2. GPT-5.1 超时链路修复](#2-gpt-51-超时链路修复)
    - [3. state\_db 端点 404 日志噪音修复](#3-state_db-端点-404-日志噪音修复)
    - [4. WatchFiles 误触发 reload 修复](#4-watchfiles-误触发-reload-修复)
    - [5. Docker 构建文件补全](#5-docker-构建文件补全)
    - [6. healthz 端点增加 PG 诊断](#6-healthz-端点增加-pg-诊断)
  - [2026-03-05：POST /runs 异步化重构 \& 前端适配](#2026-03-05post-runs-异步化重构--前端适配)
    - [1. 后端 POST /runs 异步后台线程执行](#1-后端-post-runs-异步后台线程执行)
    - [2. 新增 GET /threads/{id}/run\_status 端点](#2-新增-get-threadsidrun_status-端点)
    - [3. 409 重复提交防护](#3-409-重复提交防护)
    - [4. 前端适配（代理超时 + Hook 简化 + 测试更新）](#4-前端适配代理超时--hook-简化--测试更新)
  - [2026-03-08：Resilient Fallback 误触发修复 \& 质量控制策略](#2026-03-08resilient-fallback-误触发修复--质量控制策略)
  - [2026-03-08：前端实时 Graph 阶段追踪 \& 开发工具链修复 \& 文档整理](#2026-03-08前端实时-graph-阶段追踪--开发工具链修复--文档整理)
    - [1. 前端 Graph 调用链实时阶段追踪](#1-前端-graph-调用链实时阶段追踪)
    - [2. 前端启动 EADDRINUSE 端口冲突修复](#2-前端启动-eaddrinuse-端口冲突修复)
    - [3. troubleshooting.md 全量整理](#3-troubleshootingmd-全量整理)
  - [附录：后端修改文件速查](#附录后端修改文件速查)
  - [附录：环境变量速查](#附录环境变量速查)

---

## 2026-03-04：首次部署调试 & 生产修复

本日修复了从本地开发到 Docker 部署过程中暴露的 6 个后端问题。

### 1. PostgreSQL 持久化降级修复

**问题**: `POST /runs` 返回 200 且包含完整结果，但 Postgres `run_states_latest` 表中 0 行记录。重启编排层后数据丢失。

**根因**:
- Docker `depends_on` 只等容器 start 不等 ready → Postgres 未 ready 时 `PostgresClient` 连接失败 → `_available = False` → 永久降级到 `InMemoryPostgres`
- 本机 uvicorn 残留进程占用 8000 端口，curl 请求被旧进程截获

**修改文件**:

| 文件 | 改动 |
|---|---|
| `docker-compose.yml` | 为 postgres 添加 `healthcheck`（`pg_isready -U postgres -d shannon`, interval 3s, retries 10）；orchestration 服务添加 `depends_on: condition: service_healthy` |

**关键配置**:
```yaml
postgres:
  healthcheck:
    test: ["CMD-SHELL", "pg_isready -U postgres -d shannon"]
    interval: 3s
    timeout: 3s
    retries: 10

orchestration:
  depends_on:
    postgres:
      condition: service_healthy
```

**验证**:
```bash
docker exec -it shannon-postgres-1 psql -U postgres -d shannon -c "select now();"
curl -s http://127.0.0.1:8000/healthz   # 预期: {"status":"ok","pg_available":true}
```

---

### 2. GPT-5.1 超时链路修复

**问题**: `AGENT_CALL_STARTED` 后 LLM 日志显示 `[error:gpt-5.1] APITimeoutError: Request timed out.`，工作流无法完成。

**根因**: `/agent/run` 和 `/v1/responses` 端点调用 `OpenAIClient.complete()` 时未传 `request_timeout`，落入 SDK 默认 45s。gpt-5.1 复杂任务需 60-180s。

**修改文件**:

| 文件 | 改动 |
|---|---|
| `src/shannon/llm_service/main.py` | 新增 `_run_request_timeout()` 和 `_responses_request_timeout()` 函数 |
| `.env` | 新增 `OPENAI_TIMEOUT_SECONDS=120` |

**新增函数**:

```python
def _run_request_timeout(model_tier: str) -> float:
    """按 model tier 返回 /agent/run 的 OpenAI SDK 请求级超时。"""
    # 环境变量覆盖: OPENAI_RUN_TIMEOUT_SECONDS / OPENAI_RUN_TIMEOUT_SECONDS_{TIER}
    # 默认值: small=90s, medium=120s, large=180s
    # clamp: [30s, 600s]

def _responses_request_timeout(model_tier: str) -> float:
    """按 model tier 返回 /v1/responses 的 OpenAI SDK 请求级超时。"""
    # 环境变量覆盖: OPENAI_RESPONSES_TIMEOUT_SECONDS
    # 默认值: small=90s, medium=120s, large=240s
    # clamp: [30s, 600s]
```

**代码调用点改动**:
```python
# /agent/run — 修复前
content = client.complete(prompt=prompt, model=model, temperature=0.2, system_prompt=system_prompt)

# /agent/run — 修复后
run_timeout = _run_request_timeout(task.model_tier)
content = client.complete(prompt=prompt, model=model, temperature=0.2,
                          system_prompt=system_prompt, request_timeout=run_timeout)

# /v1/responses — 修复后
resp_timeout = _responses_request_timeout(req.model_tier or "large")
content = client.complete(req.prompt, model=resolved_model, temperature=req.temperature,
                          system_prompt=req.system_prompt, request_timeout=resp_timeout)
```

**超时配置全景**:

| 环节 | 配置项 | 修复前 | 修复后 |
|---|---|---|---|
| OpenAI SDK 客户端级 | `OPENAI_TIMEOUT_SECONDS` | 45s | **120s** |
| `/agent/run` (large) | `_run_request_timeout()` | 45s | **180s** |
| `/v1/responses` (large) | `_responses_request_timeout()` | 45s | **240s** |
| `/agent/decompose` (large) | `_decompose_generation_limits()` | 120s | 120s（原已正确） |
| 编排层 httpx → LLM Service | `ORCH_LLM_SERVICE_TIMEOUT_SECONDS` | 120s | 120s |
| 编排层 httpx → responses | `ORCH_LLM_SERVICE_TIMEOUT_RESPONSES_SECONDS` | 300s | 300s |

---

### 3. state_db 端点 404 日志噪音修复

**问题**: 编排层日志中 `/threads/{id}/state_db` 持续输出大量 404 Not Found（前端每 1.5s 轮询，工作流运行期间 PG 尚无数据）。

**根因**: 原端点在未找到数据时抛出 `HTTPException(404)`，但 `save_thread_state()` 仅在 `POST /runs` 完成后才写入 PG。

**修改文件**:

| 文件 | 改动 |
|---|---|
| `src/shannon/orchestration/orchestrator/app.py` | `state_db` 端点未找到数据时返回 `{"thread_id": ..., "state": null}` 而非 404 |

```python
# 修复前
if state_row is None:
    raise HTTPException(status_code=404, detail="state 不存在")

# 修复后
if state_row is None:
    return {"thread_id": thread_id, "state": None}
```

---

### 4. WatchFiles 误触发 reload 修复

**问题**: `uvicorn --reload` 检测到 `tests/`、`desktop/`、`migrations/` 变更，触发不必要的服务重启。

**修改文件**:

| 文件 | 改动 |
|---|---|
| `Makefile` | `run-orchestration` 和 `run-llm` 目标添加 `--reload-exclude` |

```makefile
# 修复前
PYTHONPATH=${PYTHONPATH} ${PYTHON} -m uvicorn shannon.orchestration.main:app --reload --port 8000

# 修复后
PYTHONPATH=${PYTHONPATH} ${PYTHON} -m uvicorn shannon.orchestration.main:app --reload --port 8000 \
  --reload-exclude 'tests/*' --reload-exclude 'desktop/*' --reload-exclude 'migrations/*'
```

LLM Service `run-llm` 目标同样添加了排除规则。

---

### 5. Docker 构建文件补全

**问题**: 容器内找不到 `migrations/postgres/*.sql` 和配置文件，自动迁移和配置加载失败。

**修改文件**:

| 文件 | 改动 |
|---|---|
| `deploy/docker/Dockerfile.orchestration` | 添加 `COPY migrations ./migrations` 和 `COPY config ./config` |
| `deploy/docker/Dockerfile.llm_service` | 同上 |

```dockerfile
COPY src ./src
COPY migrations ./migrations    # ← 新增
COPY config ./config            # ← 新增
```

---

### 6. healthz 端点增加 PG 诊断

**问题**: 原 `/healthz` 仅返回 `{"status":"ok"}`，无法判断 Postgres 是否正常连接。

**修改文件**:

| 文件 | 改动 |
|---|---|
| `src/shannon/orchestration/orchestrator/app.py` | `/healthz` 返回 `pg_available` 字段 |

```python
@app.get("/healthz")
def healthz():
    _pg = getattr(app.state, "pg_client", None)
    return {"status": "ok", "pg_available": _pg.available if _pg else False}
```

---

## 2026-03-05：POST /runs 异步化重构 & 前端适配

本日修复了 `POST /runs` 同步阻塞 uvicorn 单 worker 导致全站 502 的严重问题，并完成前端适配。同日还进行了前端 Graph 模块三层架构重构（详见 [troubleshooting.md → Issue #8](troubleshooting.md#issue-8前端-graph-模块三层架构重构2026-03-05)）。

**背景**: 用户使用 `deep` 策略生成训练数据时，`graph.invoke()` 同步执行耗时 16+ 小时，阻塞了 uvicorn 唯一的事件循环线程，导致 `healthz`、`/threads/{id}/state`、SSE 流等所有请求排队超时返回 502。

### 1. 后端 POST /runs 异步后台线程执行

**问题**: `POST /runs` 直接调用同步 `graph.invoke(state_in, config)`，在单 worker + `--reload` 开发模式下阻塞整个服务。

**修改文件**:

| 文件 | 改动 |
|---|---|
| `src/shannon/orchestration/orchestrator/app.py` | `POST /runs` 从同步阻塞改为 **202 Accepted + `threading.Thread(daemon=True)` 后台执行**；新增 `_run_registry` 运行注册表 + `_run_registry_lock`；版本升至 `0.3.0` |

**关键改动**:
```python
_run_registry: Dict[str, Dict[str, Any]] = {}
_run_registry_lock = threading.Lock()

@app.post("/runs", status_code=202)
def start_run(req: RunRequest):
    # 立即返回 202，后台执行 graph.invoke()
    thread = threading.Thread(target=_background_run, name=f"run-{thread_id}", daemon=True)
    thread.start()
    return {"thread_id": thread_id, "status": "accepted"}
```

`_background_run()` 内部负责：
- 调用 `graph.invoke(state_in, config)` 执行完整工作流
- 完成后推送 `WORKFLOW_COMPLETED` SSE 事件
- 更新 `_run_registry` 状态为 `completed`/`failed`
- 异常时推送 `WORKFLOW_FAILED` 事件并记录错误

### 2. 新增 GET /threads/{id}/run_status 端点

**修改文件**:

| 文件 | 改动 |
|---|---|
| `src/shannon/orchestration/orchestrator/app.py` | 新增 `GET /threads/{thread_id}/run_status` 端点 |

**响应格式**:
```json
{"thread_id": "xxx", "run_status": "running|completed|failed|unknown", "error": null}
```

### 3. 409 重复提交防护

**修改文件**:

| 文件 | 改动 |
|---|---|
| `src/shannon/orchestration/orchestrator/app.py` | `POST /runs` 发送前检查 `_run_registry`，同一 thread 有 running 状态时返回 `409 Conflict` |

```python
with _run_registry_lock:
    existing = _run_registry.get(thread_id)
    if existing and existing["status"] == "running":
        raise HTTPException(409, f"thread {thread_id} 已有运行中的工作流")
```

### 4. 前端适配（代理超时 + Hook 简化 + 测试更新）

| 文件 | 改动 |
|---|---|
| `desktop/lib/backend.ts` | 新增 `PROXY_TIMEOUT_MS = 10_000` + `AbortController`，防止 Next.js 代理挂起 |
| `desktop/hooks/useRunController.ts` | `RunResult` 从 `{response, timedOut}` 简化为 `{accepted: boolean}`；新增 409 中文错误提示 |
| `desktop/app/page.tsx` | `onSend` 回调适配 `accepted` 模式 |
| `desktop/lib/api/client.ts` | `RUN_TIMEOUT_MS` 从 120s 降至 15s（POST /runs 现在立即返回） |
| `desktop/tests/component/chat-flow.test.tsx` | `/api/runs` mock 从 200 改为 202 |
| `desktop/tests/e2e/chat-workflow.spec.ts` | 两个测试用例 mock 从 200 改为 202 |

**验证结果**:

| 测试项 | 结果 |
|---|---|
| `POST /runs` 返回 202 | ✅ 14ms 内返回 |
| 后台线程完整执行 | ✅ refine→decompose→run→responses |
| `healthz` 不阻塞 | ✅ deep 策略运行期间 5ms 响应 |
| 409 重复提交 | ✅ 同一 thread 二次提交被拒 |
| TypeScript 类型检查 | ✅ 全部修改文件零错误 |

---

## 2026-03-08：Resilient Fallback 误触发修复 & 质量控制策略

本日修复了 `POST /runs` 执行后 task 未真正调度 LLM 而全部走 resilient fallback 模板化输出的问题，并引入 `strict_output` / `quality_mode` 两个质量控制参数。

### 1. 收窄 `_is_transform_only_task()` 匹配条件

**问题**: 该函数使用 `"generate"`、`"format"`、`"summarize"` 等泛词作为匹配标记，导致大量需要 LLM 实质生成的任务被误判为"纯转换任务"，跳过 LLM 调用直接返回模板化文本。

**根因**: transform_markers 列表过宽；`"generate"` 几乎会匹配任何含 "Generate" 标题的任务（如 "Generate JSONL QA"），即使该任务需要 LLM 基于上游证据做实质内容生成。

**修改文件**:

| 文件 | 改动 |
|---|---|
| `src/shannon/llm_service/main.py` | 移除泛词 `"generate"`、`"format"`、`"summarize"`、`"training sample"`；保留强信号 `"jsonl"`、`"reformat"`、`"convert format"`、`"sort"`、`"select the top"`、`"extract the abstract"` |

**修改前**:
```python
transform_markers = [
    "generate", "jsonl", "format", "summarize",
    "sort", "select the top", "extract the abstract", "training sample",
]
```

**修改后**:
```python
transform_markers = [
    "jsonl", "reformat", "convert format",
    "sort", "select the top", "extract the abstract", "training sample",
]
```

### 2. 转换任务确定性 fallback 短路受 `strict_output` 控制

**问题**: `_is_transform_only_task()` 判定为 True 且有 `previous_results` 时，`/agent/run` 无条件跳过 LLM 调用，直接返回模板化文本。用户无法强制要求 LLM 执行真实生成。

**修改文件**:

| 文件 | 改动 |
|---|---|
| `src/shannon/llm_service/main.py` | `AgentRunRequest` 新增 `strict_output: bool = False`；转换任务短路仅在 `strict_output=False` 时生效 |
| `src/shannon/orchestration/orchestrator/state.py` | `ResearchState` 新增 `strict_output: bool` 字段 |
| `src/shannon/orchestration/orchestrator/app.py` | `POST /runs` 入参透传 `strict_output` |
| `src/shannon/orchestration/orchestrator/graph.py` | `execute_node` → `_execute_single_task` 传递 `strict_output` |
| `src/shannon/orchestration/orchestrator/llm_service_client.py` | `run_task()` HTTP 请求体增加 `strict_output` |

```python
# 修复前
if _is_transform_only_task(task) and previous_results:
    # 无条件走确定性 fallback

# 修复后
if _is_transform_only_task(task) and previous_results and not req.strict_output:
    # 仅非 strict 模式走确定性 fallback
```

### 3. 低价值输出走 `quality_mode` 策略

**问题**: LLM 返回低价值内容（匹配 `_is_low_value_content()`）时，`status` 从 `"error"` 被静默改写为 `"ok"`、`quality_status` 设为 `"ok"`。编排层的 `verify_merge_node` 看到 `status="ok"` 不会触发重试，低质量输出被静默接受并传递给下游。

**修改文件**:

| 文件 | 改动 |
|---|---|
| `src/shannon/llm_service/main.py` | `AgentRunRequest` 新增 `quality_mode: str = "best_effort"`；新增分支策略 |
| `src/shannon/orchestration/orchestrator/state.py` | `ResearchState` 新增 `quality_mode: str` 字段 |
| `src/shannon/orchestration/orchestrator/app.py` | `POST /runs` 入参透传 `quality_mode` |
| `src/shannon/orchestration/orchestrator/graph.py` | `execute_node` → `_execute_single_task` 传递 `quality_mode` |
| `src/shannon/orchestration/orchestrator/llm_service_client.py` | `run_task()` HTTP 请求体增加 `quality_mode` |

```python
# 修复前
if status == "error" and error_message in {"low_relevance_output", "empty_output"}:
    content = _build_resilient_fallback_content(...)
    status = "ok"
    quality_status = "ok"  # 伪装为成功

# 修复后
if status == "error" and error_message in {"low_relevance_output", "empty_output"}:
    if req.quality_mode == "strict":
        pass  # 保持 error，编排层触发重试
    else:  # best_effort
        content = _build_resilient_fallback_content(...)
        status = "ok"
        quality_status = "degraded"  # 标记为降级而非伪装 ok
        retrieval_trace["warnings"].append("fallback_degraded")
```

### 4. 依赖收敛深度限制器修复

**问题**: 收窄 `_is_transform_only_task()` 后，`_converge_task_dependencies` 的深度限制器不再允许 research → synthesis → transform 标准三层 DAG，导致 JSONL 任务与 merge 任务的依赖链被错误打断。

**修改文件**:

| 文件 | 改动 |
|---|---|
| `src/shannon/llm_service/main.py` | 引入 shallow_synthesis（仅依赖根层的汇总任务）概念，允许 transform 任务依赖浅层汇总任务 |
| `tests/unit/test_llm_service_main.py` | 更新 DAG 深度断言：从严格 2 层改为验证深度 ≤ 3 + 无超 3 层链 |

```python
# 修复后：允许 research → synthesis → transform 三层流水线
task_by_id = {str(t.id): t for t in tasks}
shallow_synthesis = set()
for tid in synthesis_set:
    t = task_by_id.get(tid)
    if t is not None and all(dep in root_set for dep in (t.deps or [])):
        shallow_synthesis.add(tid)

if _is_transform_only_task(task):
    allowed = root_set | shallow_synthesis  # 可依赖浅层汇总
else:
    allowed = root_set  # 仅依赖根层
```

**验证**: 全部 42 个单元测试通过。

**调用示例**:
```bash
# 默认行为（向后兼容）
curl -X POST http://127.0.0.1:8000/runs -d '{"user_request": "...", "strategy": "deep"}'

# 强制 LLM 生成 + 严格质量控制
curl -X POST http://127.0.0.1:8000/runs -d '{
  "user_request": "...",
  "strategy": "deep",
  "strict_output": true,
  "quality_mode": "strict"
}'
```

---

## 2026-03-08：前端实时 Graph 阶段追踪 & 开发工具链修复 & 文档整理

本次补充记录本轮对话中完成的前端实时调用链、开发工具链和文档方面的改动。

### 1. 前端 Graph 调用链实时阶段追踪

**问题**: 前端右侧 CallGraph 在工作流完成前不显示任何节点，用户无法感知当前执行阶段。仅在 `WORKFLOW_COMPLETED` 后一次性渲染全部调用链。

**根因**: `buildGraphFromEvents()` 仅处理 `AGENT_CALL_*` 事件，忽略了 `NODE_STARTED` / `NODE_COMPLETED` / `NODE_FAILED` 等阶段事件。`GraphLegend` 组件为静态渲染。

**修改文件**:

| 文件 | 改动 |
|---|---|
| `desktop/lib/types.ts` | `GraphNodeData.kind` 新增 `"phase"` 联合类型 |
| `desktop/lib/events/graph.ts` | 新增 6 个 phase 节点（refine→decompose→schedule→execute→verify→finalize），处理 `NODE_STARTED/COMPLETED/FAILED` 实时更新阶段状态；`WORKFLOW_STARTED/COMPLETED/FAILED` 事件更新整体状态 |
| `desktop/components/graph/GraphLegend.tsx` | 从静态图例重写为实时进度条，接收 `nodes` prop，running 状态带 pulse 动画 |
| `desktop/app/page.tsx` | 向 `<GraphLegend>` 传递 `nodes={eventUi.nodes}` |
| `desktop/app/globals.css` | 新增 `.legend-phases`、`.legend-phase-item`、`.legend-phase-arrow`、`@keyframes pulse` |

**关键改动**:

```typescript
// graph.ts — 新增 phase 节点（始终渲染在图表顶部）
const phaseOrder = ["refine", "decompose", "schedule", "execute", "verify", "finalize"];
for (const phase of phaseOrder) {
  upsertNode(`phase:${phase}`, { label: phaseLabels[phase], kind: "phase", status: "idle" }, ...);
}

// 实时响应 NODE_STARTED 事件
if (event.type === "NODE_STARTED") {
  upsertNode(`phase:${nodeName}`, { ..., status: "running" }, ...);
}
```

```tsx
// GraphLegend.tsx — 实时进度条（简化示意）
const phaseNodes = nodes.filter(n => n.data.kind === "phase");
// 精炼 → 分解 → 调度 → 执行 → 验证 → 汇总
//  ●      ●      ●      ⠿      ○      ○
// 完成   完成   完成   运行中  等待   等待
```

---

### 2. 前端启动 EADDRINUSE 端口冲突修复

**问题**: 执行 `start-dev.sh` 时报 `Error: listen EADDRINUSE: address already in use :::3000`。上一次 Next.js 进程未正常退出，残留进程占用端口。

**修改文件**:

| 文件 | 改动 |
|---|---|
| `desktop/start-dev.sh` | 启动前自动释放 3000 端口：`lsof -ti :3000 2>/dev/null \| xargs kill -9 2>/dev/null && sleep 1` |

---

### 3. troubleshooting.md 全量整理

**改动**: 将 `docs/troubleshooting.md` 从最初的 3 个 Issue 扩展到 9 个 Issue 的完整故障记录，覆盖本轮对话涉及的所有修复：

| Issue # | 标题 |
|---|---|
| #1 | PostgreSQL 持久化降级 |
| #2 | 前端 TypeScript + Node.js 兼容性 |
| #3 | gpt-5.1 APITimeoutError |
| #4 | state_db 404 日志噪音 |
| #5 | WatchFiles 误触发 reload |
| #6 | EADDRINUSE 端口冲突 |
| #7 | 前端 Graph 非实时更新 |
| #8 | 前端 Graph 三层架构重构（03-05） |
| #9 | POST /runs 同步阻塞致 502（03-05） |

同步更新了启动流程、环境变量速查等附录章节。

---

## 附录：后端修改文件速查

| 日期 | 文件 | 改动类型 |
|---|---|---|
| 03-04 | `docker-compose.yml` | postgres healthcheck + depends_on |
| 03-04 | `deploy/docker/Dockerfile.orchestration` | COPY migrations + config |
| 03-04 | `deploy/docker/Dockerfile.llm_service` | COPY migrations + config |
| 03-04 | `src/shannon/orchestration/orchestrator/app.py` | healthz PG 诊断 + state_db 返回 null 替代 404 |
| 03-04 | `src/shannon/llm_service/main.py` | 新增 `_run_request_timeout()` + `_responses_request_timeout()` |
| 03-04 | `Makefile` | `--reload-exclude` 排除非源码目录 |
| 03-04 | `.env` | `OPENAI_TIMEOUT_SECONDS=120` |
| 03-05 | `src/shannon/orchestration/orchestrator/app.py` | POST /runs 异步化：202 + threading.Thread + _run_registry + run_status 端点 + 409 防护 |
| 03-05 | `desktop/lib/backend.ts` | 新增 PROXY_TIMEOUT_MS + AbortController |
| 03-05 | `desktop/hooks/useRunController.ts` | RunResult 简化为 {accepted} |
| 03-05 | `desktop/app/page.tsx` | onSend 适配 accepted 模式 |
| 03-05 | `desktop/lib/api/client.ts` | RUN_TIMEOUT_MS 120s→15s |
| 03-05 | `desktop/tests/component/chat-flow.test.tsx` | mock 200→202 |
| 03-05 | `desktop/tests/e2e/chat-workflow.spec.ts` | mock 200→202 |
| 03-08 | `src/shannon/llm_service/main.py` | 收窄 transform 匹配 + strict_output/quality_mode + 依赖收敛修复 |
| 03-08 | `src/shannon/orchestration/orchestrator/state.py` | ResearchState 新增 strict_output / quality_mode 字段 |
| 03-08 | `src/shannon/orchestration/orchestrator/app.py` | POST /runs 透传 strict_output / quality_mode |
| 03-08 | `src/shannon/orchestration/orchestrator/graph.py` | execute_node 透传 strict_output / quality_mode |
| 03-08 | `src/shannon/orchestration/orchestrator/llm_service_client.py` | run_task() 请求体增加 strict_output / quality_mode |
| 03-08 | `tests/unit/test_llm_service_main.py` | DAG 深度断言更新为 ≤3 层 + 祖父节点校验 |
| 03-08 | `desktop/lib/types.ts` | `GraphNodeData.kind` 新增 `"phase"` |
| 03-08 | `desktop/lib/events/graph.ts` | 新增 6 个 phase 节点 + NODE_STARTED/COMPLETED/FAILED 实时处理 |
| 03-08 | `desktop/components/graph/GraphLegend.tsx` | 重写为实时进度条 |
| 03-08 | `desktop/app/page.tsx` | 向 GraphLegend 传递 nodes prop |
| 03-08 | `desktop/app/globals.css` | 新增 legend-phases 动画样式 |
| 03-08 | `desktop/start-dev.sh` | 启动前自动 kill 3000 端口 |
| 03-08 | `docs/troubleshooting.md` | 扩展至 Issue #1-#9 全量故障记录 |

---

## 附录：环境变量速查

```bash
# 必要配置
OPENAI_API_KEY=sk-xxx

# 超时配置（03-04 新增/修改）
OPENAI_TIMEOUT_SECONDS=120                     # SDK 客户端级超时（默认 45s → 120s）
# OPENAI_RUN_TIMEOUT_SECONDS=180               # /agent/run 超时覆盖（默认按 tier 自动）
# OPENAI_RESPONSES_TIMEOUT_SECONDS=240          # /v1/responses 超时覆盖（默认按 tier 自动）

# 数据层
POSTGRES_DSN=postgresql://postgres:postgres@localhost:5432/shannon
REDIS_URL=redis://localhost:6379/0
POSTGRES_AUTO_MIGRATE=true
```
