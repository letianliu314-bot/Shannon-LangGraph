# Shannon 项目 — 故障诊断与修复记录

> 最后更新：2026-03-05  
> 维护范围：后端基础设施 + 前端编译 + 运行时 API 超时 + 日志治理 + 前端实时调用链 + 前端图模块重构 + 后端异步运行架构

---

## 目录

- [Shannon 项目 — 故障诊断与修复记录](#shannon-项目--故障诊断与修复记录)
  - [目录](#目录)
  - [Issue #1：PostgreSQL 持久化降级为内存模式](#issue-1postgresql-持久化降级为内存模式)
    - [现象](#现象)
    - [根因](#根因)
    - [解决方案（已实施）](#解决方案已实施)
    - [验证命令](#验证命令)
  - [Issue #2：前端 TypeScript 编译失败 + Node.js 兼容性](#issue-2前端-typescript-编译失败--nodejs-兼容性)
    - [现象](#现象-1)
    - [根因](#根因-1)
    - [解决方案（已实施）](#解决方案已实施-1)
    - [验证命令](#验证命令-1)
  - [Issue #3：gpt-5.1 APITimeoutError](#issue-3gpt-51-apitimeouterror)
    - [现象](#现象-2)
    - [根因](#根因-2)
    - [解决方案（已实施 ✅）](#解决方案已实施-)
    - [超时配置最终全景](#超时配置最终全景)
    - [附加发现：错误静默问题](#附加发现错误静默问题)
  - [Issue #4：state\_db 端点大量 404 日志噪音](#issue-4state_db-端点大量-404-日志噪音)
    - [现象](#现象-3)
    - [根因](#根因-3)
    - [解决方案（已实施 ✅）](#解决方案已实施--1)
  - [Issue #5：WatchFiles 频繁误触发 reload](#issue-5watchfiles-频繁误触发-reload)
    - [现象](#现象-4)
    - [根因](#根因-4)
    - [解决方案（已实施 ✅）](#解决方案已实施--2)
  - [Issue #6：前端启动 EADDRINUSE 端口冲突](#issue-6前端启动-eaddrinuse-端口冲突)
    - [现象](#现象-5)
    - [根因](#根因-5)
    - [解决方案（已实施 ✅）](#解决方案已实施--3)
  - [Issue #7：前端 Graph 调用链非实时更新](#issue-7前端-graph-调用链非实时更新)
    - [现象](#现象-6)
    - [根因](#根因-6)
    - [解决方案（已实施 ✅）](#解决方案已实施--4)
  - [Issue #8：前端 Graph 模块三层架构重构（2026-03-05）](#issue-8前端-graph-模块三层架构重构2026-03-05)
    - [背景与目标](#背景与目标)
    - [架构改动](#架构改动)
    - [修改文件清单](#修改文件清单)
    - [测试验证](#测试验证)
    - [已知限制](#已知限制)
  - [Issue #9：POST /runs 同步阻塞致 502（2026-03-05）](#issue-9post-runs-同步阻塞致-5022026-03-05)
    - [现象](#现象-7)
    - [根因](#根因-7)
    - [解决方案（已实施 ✅）](#解决方案已实施--5)
      - [1. 后端：异步后台线程执行 (`app.py`)](#1-后端异步后台线程执行-apppy)
      - [2. 前端代理超时 (`backend.ts`)](#2-前端代理超时-backendts)
      - [3. 前端 Hook 简化 (`useRunController.ts`)](#3-前端-hook-简化-useruncontrollerts)
      - [4. 客户端超时缩减 (`client.ts`)](#4-客户端超时缩减-clientts)
    - [修改文件清单](#修改文件清单-1)
    - [验证结果](#验证结果)
    - [已知限制](#已知限制-1)
  - [快速参考：完整启动流程](#快速参考完整启动流程)
  - [环境变量速查（.env）](#环境变量速查env)

---

## Issue #1：PostgreSQL 持久化降级为内存模式

### 现象

- `POST /runs` 返回 200 且包含完整结果
- `GET /threads/{id}/state_db` 可从 API 获取数据
- 但 Postgres `run_states_latest` 表中 **0 行记录**
- 重启编排层后数据丢失

### 根因

1. **Docker 启动顺序竞争**: `PostgresClient` 是模块级单例，在 Python import 时立即创建连接。原 `depends_on` 只等容器 start 不等 ready → Postgres 未 ready 时连接失败 → `_available = False` → 永久降级到 `InMemoryPostgres`，不会重试。

2. **本机 uvicorn 残留进程占用 8000 端口**: 之前本机直接运行的 uvicorn 仍在监听 8000，curl 请求被旧进程截获而非发送到 Docker 容器。

3. **Dockerfile 缺少 migrations 目录**: 容器内找不到 `migrations/postgres/*.sql`，自动迁移只能靠内置 `BOOTSTRAP_SQL`。

### 解决方案（已实施）

| 修复项 | 文件 | 改动 |
|---|---|---|
| Postgres healthcheck | `docker-compose.yml` | 添加 `healthcheck` + `depends_on: condition: service_healthy` |
| 复制 migrations 到容器 | `deploy/docker/Dockerfile.orchestration` | 添加 `COPY migrations ./migrations` 和 `COPY config ./config` |
| 同步修复 LLM Dockerfile | `deploy/docker/Dockerfile.llm_service` | 同上 |
| healthz 增加 PG 诊断 | `src/shannon/orchestration/orchestrator/app.py` | `/healthz` 返回 `pg_available` 字段 |
| 杀掉残留进程 | 手动操作 | `kill` 占用 8000 端口的旧 uvicorn 进程 |

### 验证命令

```bash
# 确认 Postgres 可达
docker exec -it shannon-postgres-1 psql -U postgres -d shannon -c "select now();"

# 确认编排层 PG 连接正常
curl -s http://127.0.0.1:8000/healthz
# 预期: {"status":"ok","pg_available":true}

# 写入测试
curl -s -X POST http://127.0.0.1:8000/runs -H 'content-type: application/json' \
  -d '{"thread_id":"persist-test","user_request":"ping","strategy":"quick"}'

# 验证落库
docker exec -it shannon-postgres-1 psql -U postgres -d shannon \
  -c "select thread_id,status,updated_at from run_states_latest where thread_id='persist-test';"

# 重启后验证持久化
docker compose restart orchestration
curl -s http://127.0.0.1:8000/threads/persist-test/state_db
```

---

## Issue #2：前端 TypeScript 编译失败 + Node.js 兼容性

### 现象

- `npm run typecheck` 退出码 2（9 个 TypeScript 错误）
- `npm run build` 失败
- `next dev` 在 Node.js v25.6.0 下首页编译卡死超过 2 分钟

### 根因

**TypeScript 错误（9 个，2 类根因）：**

1. **`GraphNodeData` 不满足 `Record<string, unknown>` 约束**（7 处）

   `@xyflow/react` 的 `Node<T>` 泛型要求 `T extends Record<string, unknown>`。TypeScript 的 `interface` 不具备隐式索引签名，`interface GraphNodeData` 不满足该约束。

   受影响文件: `app/page.tsx`, `components/graph/CallGraph.tsx`, `components/graph/NodeDetails.tsx`, `lib/events/graph.ts`, `lib/events/reducer.ts`

2. **`reduce()` 返回 `unknown`**（2 处）

   `app/page.tsx` 中 `items.reduce(...)` 的累加器未声明类型，TypeScript 推断为 `unknown`。

**Node.js 兼容性：**

Next.js 14.2 官方支持 Node 18-20，系统安装的 Node v25.6.0 过新，导致 webpack 编译卡死。

### 解决方案（已实施）

| 修复项 | 文件 | 改动 |
|---|---|---|
| GraphNodeData 改为 type alias | `desktop/lib/types.ts` | `interface GraphNodeData` → `type GraphNodeData = {...; [key: string]: unknown }` |
| reduce 加泛型 | `desktop/app/page.tsx` | `items.reduce(...)` → `items.reduce<EventUiState>(...)` |
| 补全 EventUiState 导入 | `desktop/app/page.tsx` | 添加 `import { EventUiState, ... }` |
| 安装 Node 20 LTS | 系统级 | `brew install node@20` |
| 前端启动脚本 | `desktop/start-dev.sh` | 创建脚本，优先使用 Node 20，自动切换 cwd |

### 验证命令

```bash
# TypeScript 检查
cd desktop && npx tsc --noEmit
# 预期: 无错误输出，退出码 0

# 前端启动
bash desktop/start-dev.sh
# 预期: Next.js 14.2.35 在 http://localhost:3000 启动
```

---

## Issue #3：gpt-5.1 APITimeoutError

### 现象

- **Thread**: `thread-1772603428174`
- **用户请求**: "请在互联网搜索5条主流的ai市场调研方案，然后分析每一个方案的优缺点后，给我汇总一个你认为最好的市场调研方案"
- **前端错误**: `[error:gpt-5.1] APITimeoutError: Request timed out.`
- 编排层日志显示 `/threads/.../state_db` 大量 **404 Not Found**
- LLM 服务日志 HTTP 200，但错误封装在响应体字符串中

### 根因

**超时链路追踪（由外到内）：**

```
前端 POST /runs
  ▼
编排层 graph.invoke() ← 无超时，阻塞等待
  ▼
LLMServiceClient (httpx) ← 120s
  ▼
LLM Service /agent/run → OpenAIClient.complete()
  ↓ 未传 request_timeout → 继承 SDK 客户端级 45s (OPENAI_TIMEOUT_SECONDS 默认)
  ↓ gpt-5.1 复杂 prompt 需 60-180s
  → APITimeoutError: Request timed out.
  → 被 openai_client.py 吞为 "[error:gpt-5.1] APITimeoutError: ..."
  → agent_run 返回 status="error" → verify 重试 2 次仍超时 → 全部失败
```

**直接原因**: `/agent/run` 和 `/v1/responses` 端点调用 `OpenAIClient.complete()` 时**未传** `request_timeout`，落入 SDK 默认 **45s**。

### 解决方案（已实施 ✅）

**环境变量修复**（`.env`）：
```bash
OPENAI_TIMEOUT_SECONDS=120    # SDK 客户端级兜底
```

**代码修复**（`src/shannon/llm_service/main.py`）：

新增两个超时函数，按 model tier 分层设置 OpenAI SDK 请求级超时：

| 函数 | 端点 | small | medium | large | 环境变量覆盖 |
|---|---|---|---|---|---|
| `_run_request_timeout()` | `/agent/run` | 90s | 120s | **180s** | `OPENAI_RUN_TIMEOUT_SECONDS` |
| `_responses_request_timeout()` | `/v1/responses` | 90s | 120s | **240s** | `OPENAI_RESPONSES_TIMEOUT_SECONDS` |

代码改动：

```python
# /agent/run — 修复前
content = client.complete(prompt=prompt, model=model, temperature=0.2, system_prompt=system_prompt)

# /agent/run — 修复后
run_timeout = _run_request_timeout(task.model_tier)
content = client.complete(prompt=prompt, model=model, temperature=0.2, system_prompt=system_prompt, request_timeout=run_timeout)

# /v1/responses — 修复后
resp_timeout = _responses_request_timeout(req.model_tier or "large")
content = client.complete(req.prompt, model=resolved_model, temperature=req.temperature,
                          system_prompt=req.system_prompt, request_timeout=resp_timeout)
```

### 超时配置最终全景

| 环节 | 配置项 | 修复前 | 修复后 |
|---|---|---|---|
| OpenAI SDK 客户端级 | `OPENAI_TIMEOUT_SECONDS` | 45s | **120s**（.env） |
| `/agent/run` (large) | `_run_request_timeout()` | 45s | **180s** |
| `/v1/responses` (large) | `_responses_request_timeout()` | 45s | **240s** |
| `/agent/decompose` (large) | `_decompose_generation_limits()` | 120s | 120s（原已正确） |
| 编排层 httpx → LLM Service | `ORCH_LLM_SERVICE_TIMEOUT_SECONDS` | 120s | 120s |
| 编排层 httpx → responses | `ORCH_LLM_SERVICE_TIMEOUT_RESPONSES_SECONDS` | 300s | 300s |

### 附加发现：错误静默问题

`openai_client.py` 的 `complete()` 将所有异常统一转为字符串返回：

```python
return f"[error:{model}] {type(exc).__name__}: {str(exc)[:120]}"
```

导致 HTTP 层面始终 200 OK，日志无 ERROR 级别输出，编排层无法区分超时与参数错误。

---

## Issue #4：state_db 端点大量 404 日志噪音

### 现象

编排层日志中 `/threads/{id}/state_db` 持续输出大量 404 Not Found，原因是前端每 1.5 秒轮询该端点，而工作流执行期间 PG 尚无数据。

```
INFO: 127.0.0.1:52158 - "GET /threads/thread-1772603428174/state_db HTTP/1.1" 404 Not Found
INFO: 127.0.0.1:52159 - "GET /threads/thread-1772603428174/state_db HTTP/1.1" 404 Not Found
… (数十行重复)
```

### 根因

原 `/threads/{id}/state_db` 端点在未找到数据时抛出 `HTTPException(404)`。但 `save_thread_state()` 仅在 `POST /runs` **完成后**才写入 PG，工作流运行期间该端点必定无数据。

### 解决方案（已实施 ✅）

**修改文件**: `src/shannon/orchestration/orchestrator/app.py`

```python
# 修复前
if state_row is None:
    raise HTTPException(status_code=404, detail="state 不存在")

# 修复后
if state_row is None:
    return {"thread_id": thread_id, "state": None}
```

工作流运行期间返回 `{ state: null }` 而非 404，消除日志噪音。前端 `getThreadStateDb()` 已在 `client.ts` 中对 404 做了 catch 降级，改为 200+null 后兼容无影响。

---

## Issue #5：WatchFiles 频繁误触发 reload

### 现象

编排层 `uvicorn --reload` 检测到 `tests/`、`desktop/`、`migrations/` 下的文件变更，导致服务不断重启：

```
WARNING: WatchFiles detected changes in 'tests/unit/test_orchestrator_llm_service_client.py',
 'tests/unit/test_llm_service_main.py', 'src/shannon/utils/metrics.py', ... Reloading...
```

修改测试文件或前端代码不应触发后端 reload。

### 根因

`Makefile` 中 `make run-orchestration` 和 `make run-llm` 的 uvicorn 命令未排除无关目录。

### 解决方案（已实施 ✅）

**修改文件**: `Makefile`

```makefile
# 修复前
PYTHONPATH=${PYTHONPATH} ${PYTHON} -m uvicorn shannon.orchestration.main:app --reload --port 8000

# 修复后
PYTHONPATH=${PYTHONPATH} ${PYTHON} -m uvicorn shannon.orchestration.main:app --reload --port 8000 \
  --reload-exclude 'tests/*' --reload-exclude 'desktop/*' --reload-exclude 'migrations/*'
```

LLM Service 的 `run-llm` 目标同样添加了排除规则。

---

## Issue #6：前端启动 EADDRINUSE 端口冲突

### 现象

```
Error: listen EADDRINUSE: address already in use :::3000
    at Server.setupListenHandle [as _listen2] (node:net:1908:16)
```

启动 `start-dev.sh` 时报端口 3000 已被占用。

### 根因

上一次 `start-dev.sh` 或 `npm run dev` 启动的 Next.js 进程未正常退出（Ctrl+C 后 Node 进程未完全终止，或多个终端重复启动），残留进程继续监听 3000 端口。

### 解决方案（已实施 ✅）

**修改文件**: `desktop/start-dev.sh`

```bash
# 在启动 Next.js 前自动释放端口
lsof -ti :3000 2>/dev/null | xargs kill -9 2>/dev/null && sleep 1
```

脚本启动时先杀掉任何占用 3000 端口的进程，再启动 Next.js。

**手动解决**（如不用脚本）：
```bash
lsof -ti :3000 | xargs kill -9
# 等待 1-2 秒后重新启动
bash desktop/start-dev.sh
```

---

## Issue #7：前端 Graph 调用链非实时更新

### 现象

前端右侧的 CallGraph 区域在工作流完成前不显示任何节点。用户无法看到当前执行到哪个阶段，只有 `WORKFLOW_COMPLETED` 后一次性渲染全部调用链。

### 根因

`buildGraphFromEvents()` 函数仅处理 `AGENT_CALL_*` 类型事件来构建节点，忽略了 `NODE_STARTED` / `NODE_COMPLETED` / `NODE_FAILED` 等阶段事件。由于 LLM 调用耗时较长，两次 `AGENT_CALL` 事件之间可能间隔数十秒，期间图表无任何变化。

`GraphLegend` 组件也是静态的，无法反映当前阶段。

### 解决方案（已实施 ✅）

**1. 新增工作流阶段节点** — `desktop/lib/events/graph.ts`

`buildGraphFromEvents()` 中增加 6 个 phase 节点（精炼→分解→调度→执行→验证→汇总），始终渲染在图表顶部。`NODE_STARTED/COMPLETED/FAILED` 事件实时更新对应 phase 节点状态：

```typescript
// 新增 phase 节点（始终显示）
const phaseOrder = ["refine", "decompose", "schedule", "execute", "verify", "finalize"];
for (const phase of phaseOrder) {
  upsertNode(`phase:${phase}`, { label: phaseLabels[phase], kind: "phase", status: "idle" }, ...);
}

// 实时更新
if (event.type === "NODE_STARTED") {
  upsertNode(`phase:${nodeName}`, { ..., status: "running" }, ...);
}
```

**2. GraphLegend 改为实时进度条** — `desktop/components/graph/GraphLegend.tsx`

从纯静态改为接收 `nodes` prop，实时显示每个阶段的状态（idle/running/completed/failed），running 状态带脉冲动画：

```
精炼 → 分解 → 调度 → 执行 → 验证 → 汇总
 ●      ●      ●      ⠿      ○      ○
 完成   完成   完成   运行中  等待   等待
```

**3. 类型系统扩展** — `desktop/lib/types.ts`

`GraphNodeData.kind` 新增 `"phase"` 类型。

**4. 样式适配** — `desktop/app/globals.css`

新增 `.legend-phases`、`.legend-phase-item`、`@keyframes pulse` 等样式。

---

## Issue #8：前端 Graph 模块三层架构重构（2026-03-05）

### 背景与目标

Issue #7 引入了 6 个 phase 节点用于实时显示工作流进度，但当任务数量增多（15-30 个）时图表过于拥挤，phase 节点与 task 节点混成一层，可读性下降。本次重构彻底简化图表为**三层结构**，提升大规模任务场景的可读性。

**目标：**
- 只保留三类节点：`root`（工作流入口）、`task`（每次 AGENT_CALL）、`summary`（终态汇总）
- Phase 不再进主图，改在 GraphLegend 以进度条形式显示
- 父子关系按优先级链：`parent_task_id` > `from_task_id→to_task_id` > `AGENT_HANDOFF` > 默认挂到 root
- `WORKFLOW_COMPLETED/FAILED` → 所有叶子任务节点连到 summary
- 移除边标签（保持视觉干净），详细信息在 NodeDetails 面板查看
- 移动端响应式：≤1000px 隐藏 MiniMap
- 15-30 个任务节点时仍保持可读性

### 架构改动

**前后对比：**

| 维度 | Issue #7（修复前） | Issue #8（重构后） |
|---|---|---|
| 节点类型 | orchestrator, agent, task, phase (4 种) | root, task, summary (3 种) |
| Phase 显示 | 6 个 phase 节点在主图中 | 仅在 GraphLegend 进度条显示 |
| 图表布局 | 平铺 + 简单坐标计算 | BFS 分层 + 同层居中的层级布局 |
| 父子关系 | 简单挂到 orchestrator/agent | 优先级链（parent_task_id > from_task_id > AGENT_HANDOFF > root） |
| 布局引擎 | 手动坐标 | 自定义 BFS 层级布局（替代 dagre） |
| 边标签 | 有（agent 名称等） | 无（干净视觉） |
| MiniMap | 始终显示 | 响应式（≤1000px 隐藏） |

**自定义层级布局算法：**

最初计划使用 dagre 库做自动布局，但测试发现 `@dagrejs/dagre` v2.0.4 和 `dagre` v0.8.x 都会导致 vitest 在 setup 阶段挂起（根因是 macOS 上 jsdom 的 `readFileSync` 遇到 ETIMEDOUT 文件系统超时，与 dagre 模块解析叠加后导致完全无法推进）。最终自行实现了 BFS 分层布局算法：

```
applyHierarchicalLayout(nodeMap, edges)
  1. 构建邻接表 (source → targets)
  2. 从 root 开始 BFS 分配 rank（层级深度）
  3. 按 rank 分组 → 每层节点居中排列
  4. 参数：RANK_SEP=100px, NODE_SEP=60px, MARGIN=40px
```

### 修改文件清单

| 文件 | 变更类型 | 改动说明 |
|---|---|---|
| `desktop/lib/types.ts` | 修改 | `GraphNodeData.kind` 从 `"orchestrator"\|"agent"\|"task"\|"phase"` 改为 `"root"\|"task"\|"summary"`；新增 `eventType?: string` 字段；新增 `PhaseStatusMap` 类型导出 |
| `desktop/lib/events/graph.ts` | **完全重写** | 约 320 行。自定义 BFS 层级布局；三层节点构建；phase 提取（仅供 legend）；父子优先级链；summary 节点连接叶子任务 |
| `desktop/lib/events/reducer.ts` | 修改 | `EventUiState` 新增 `phases: PhaseStatusMap` 字段；初始值 `phases: {}`；reducer 返回 `phases: graph.phases` |
| `desktop/components/graph/CallGraph.tsx` | 修改 | 新增响应式 MiniMap（`useEffect` + `window.matchMedia("(max-width: 1000px)")` 控制 `showMiniMap` 状态）；空状态提示改为中文 |
| `desktop/components/graph/GraphLegend.tsx` | 修改 | props 从 `nodes?: Node<GraphNodeData>[]` 改为 `phases?: PhaseStatusMap`；移除 `@xyflow/react` Node 导入；直接使用 phases 渲染进度条而非从图节点提取 |
| `desktop/components/graph/NodeDetails.tsx` | 修改 | 增加条件字段渲染（仅显示非空字段）；新增 "类型"(kind)、"事件类型"(eventType) 字段；所有标签中文化；error 用 `var(--danger)` 高亮 |
| `desktop/app/page.tsx` | 微调 | `<GraphLegend nodes={eventUi.nodes} />` → `<GraphLegend phases={eventUi.phases} />` |
| `desktop/tests/unit/graph-transform.test.ts` | **完全重写** | 11 个测试用例覆盖三层结构、层级坐标、状态更新、父子关系、phase 提取、边无标签等 |
| `desktop/tests/component/chat-flow.test.tsx` | 修改 | 断言从 `"research_agent"` 改为 `"task-1"`（agent 节点已不存在） |
| `desktop/tests/e2e/chat-workflow.spec.ts` | 修改 | 断言从 `"research_agent"` 改为 `"task-1"` |
| `desktop/package.json` | 修改 | 移除 `dagre`、`@dagrejs/dagre`、`@types/dagre` 三个废弃依赖 |

### 测试验证

| 测试套件 | 结果 | 备注 |
|---|---|---|
| `tests/unit/graph-transform.test.ts`（11 用例） | **全部通过** ✅ | root 始终创建、WORKFLOW_STARTED 激活、task 挂 root、三层结构、y 坐标层级、状态更新、summary 跟随终态、parent_task_id 层级边、phase 提取不入图、边无标签、root 直连 summary |
| `tests/unit/reducer.test.ts`（2 用例） | **全部通过** ✅ | phase 演进、事件去重 |
| `tests/component/chat-flow.test.tsx`（1 用例） | **失败** ❌ | `localStorage.clear is not a function` — jsdom 环境预存问题（macOS 文件系统 ETIMEDOUT），与本次改动无关 |
| TypeScript 类型检查 | **零错误** ✅ | 所有 11 个修改文件均通过 |

> **注意**: 此机器上 vitest + jsdom 环境存在间歇性 ETIMEDOUT 超时（`readFileSync` 在 macOS 上触发），单元测试需使用 `--environment node` 标志运行才可靠：
> ```bash
> npx vitest run tests/unit/graph-transform.test.ts --environment node
> ```

### 已知限制

1. **dagre 残留**: `package-lock.json` 中仍有 dagre 条目，下次 `npm install` 会自动清理；`node_modules/` 中的 dagre 目录已手动删除
2. **组件测试**: `chat-flow.test.tsx` 因 jsdom 环境问题失败（`localStorage.clear` 不可用），与本次重构无关，属于机器环境问题
3. **自定义布局**: 当前 BFS 布局不支持边交叉最小化（true dagre 功能），在复杂 DAG 场景下可能有少量边重叠

---

## Issue #9：POST /runs 同步阻塞致 502（2026-03-05）

### 现象

- 前端切换 Thread 时收到 502 Bad Gateway
- `healthz`、`/threads/{id}/state`、SSE 流等所有请求均超时
- `lsof -ti :8000` 显示 uvicorn worker 仍存活，但 `curl healthz` 无响应
- 后台日志显示单个 `POST /runs` 请求已运行 16+ 小时（deep 策略生成训练数据）

### 根因

`POST /runs` 端点直接调用 **同步** `graph.invoke(state_in, config)`，该调用可能耗时数分钟到数小时。在 uvicorn 单 worker + `--reload` 开发模式下，这个同步方法阻塞了**唯一的事件循环线程**，导致所有后续 HTTP 请求排队 → 超时 → 502。

```
                 ┌─────── uvicorn (1 worker) ─────────┐
  POST /runs ──► │ graph.invoke() [同步，16小时]        │ ◄── 被阻塞
  GET /healthz ──► │ 排队等待... → 超时 → 502            │
  GET /state ────► │ 排队等待... → 超时 → 502            │
                 └─────────────────────────────────────┘
```

### 解决方案（已实施 ✅）

#### 1. 后端：异步后台线程执行 (`app.py`)

```python
# POST /runs 改为立即返回 202 Accepted
# graph.invoke() 在 daemon thread 中执行
_run_registry: Dict[str, Dict[str, Any]] = {}
_run_registry_lock = threading.Lock()

@app.post("/runs", status_code=202)
def start_run(req: RunRequest):
    # 409 重复提交检查
    with _run_registry_lock:
        if thread_id in _run_registry and _run_registry[thread_id]["status"] == "running":
            raise HTTPException(409, f"thread {thread_id} 已有运行中的工作流")
    # 返回 202，后台执行
    threading.Thread(target=_background_run, daemon=True).start()
    return {"thread_id": thread_id, "status": "accepted"}
```

新增端点 `GET /threads/{thread_id}/run_status` 供前端轮询后台任务状态：
```json
{"thread_id": "xxx", "run_status": "running|completed|failed|unknown", "error": null}
```

#### 2. 前端代理超时 (`backend.ts`)

```typescript
const PROXY_TIMEOUT_MS = 10_000;  // Next.js 代理 10 秒超时
const controller = new AbortController();
const timer = setTimeout(() => controller.abort(), PROXY_TIMEOUT_MS);
```

#### 3. 前端 Hook 简化 (`useRunController.ts`)

```typescript
// 之前：等待同步响应 {response, timedOut}
// 现在：只检查是否被接受 {accepted: boolean}
type RunResult = { accepted: boolean };
```

#### 4. 客户端超时缩减 (`client.ts`)

```typescript
// 120s → 15s（POST /runs 现在立即返回 202）
const RUN_TIMEOUT_MS = 15_000;
```

### 修改文件清单

| 文件 | 变更类型 | 改动说明 |
|---|---|---|
| `src/shannon/orchestration/orchestrator/app.py` | **重大重构** | `POST /runs` 从同步阻塞改为 202 + `threading.Thread` 后台执行；新增 `_run_registry` 运行注册表 + `_run_registry_lock`；新增 `GET /threads/{id}/run_status` 端点；409 重复提交拒绝；版本升至 `0.3.0` |
| `desktop/lib/backend.ts` | 修改 | 新增 `PROXY_TIMEOUT_MS = 10_000` + `AbortController` 超时保护，防止 Next.js 代理挂起 |
| `desktop/hooks/useRunController.ts` | 修改 | `RunResult` 从 `{response, timedOut}` 简化为 `{accepted}`；409 中文错误提示 |
| `desktop/app/page.tsx` | 修改 | `onSend` 回调适配 `accepted` 模式 |
| `desktop/lib/api/client.ts` | 修改 | `RUN_TIMEOUT_MS` 从 120s 降至 15s |
| `desktop/tests/component/chat-flow.test.tsx` | 修改 | `/api/runs` mock 从 200 改为 202 |
| `desktop/tests/e2e/chat-workflow.spec.ts` | 修改 | 两个测试用例 mock 从 200 改为 202 |

### 验证结果

| 测试项 | 结果 | 备注 |
|---|---|---|
| `POST /runs` 返回 202 | **通过** ✅ | 14ms 内返回 `{"thread_id":"...","status":"accepted"}` |
| 后台线程运行 | **通过** ✅ | `run_status` 从 `running` → `completed`，workflow 完整执行 refine→decompose→run→responses |
| `healthz` 不阻塞 | **通过** ✅ | deep 策略运行 20+s 期间，healthz 5ms 响应 |
| 409 重复提交 | **通过** ✅ | 同一 thread 二次提交返回 `409 Conflict` |
| TypeScript 类型检查 | **零错误** ✅ | 全部 7 个修改文件均通过 |

### 已知限制

1. **内存注册表**: `_run_registry` 使用内存 `dict`，uvicorn 热重载后注册表清空。生产部署应改用 Redis
2. **daemon 线程**: `daemon=True` 意味着主进程退出时后台任务被强制终止，不保证 finally 清理。生产环境应考虑 Celery/RQ
3. **单 worker**: 开发模式下仍为单 worker + `--reload`，线程安全由 `threading.Lock` 保证。生产部署建议 `--workers 4` + 去掉 `--reload`

---

## 快速参考：完整启动流程

```bash
cd /Users/Violet/Desktop/Shannon

# 1. 数据库（Docker）
docker compose up -d redis postgres qdrant

# 2. 编排层（本地，可直接看日志）
PYTHONPATH=src python -m uvicorn shannon.orchestration.main:app --reload --port 8000 \
  --reload-exclude 'tests/*' --reload-exclude 'desktop/*' --reload-exclude 'migrations/*'

# 3. LLM 服务（本地，可直接看日志）
PYTHONPATH=src python -m uvicorn shannon.llm_service.main:app --reload --port 8001 \
  --reload-exclude 'tests/*' --reload-exclude 'desktop/*' --reload-exclude 'migrations/*'

# 4. 前端（自动释放端口 + Node 20）
bash desktop/start-dev.sh

# 5. 验证
curl -s http://localhost:8000/healthz        # 编排层 + PG 状态
curl -s http://localhost:3000 | head -1      # 前端
```

## 环境变量速查（.env）

```bash
# 必要配置
OPENAI_API_KEY=sk-xxx                          # OpenAI API 密钥

# 超时配置
OPENAI_TIMEOUT_SECONDS=120                     # OpenAI SDK 客户端级超时（默认 45s）
# OPENAI_RUN_TIMEOUT_SECONDS=180               # /agent/run 超时覆盖（默认按 tier 自动）
# OPENAI_RESPONSES_TIMEOUT_SECONDS=240          # /v1/responses 超时覆盖（默认按 tier 自动）

# 数据层
POSTGRES_DSN=postgresql://postgres:postgres@localhost:5432/shannon
REDIS_URL=redis://localhost:6379/0
POSTGRES_AUTO_MIGRATE=true
```
