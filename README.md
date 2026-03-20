# Shannon-LangGraph

> **Version 0.3.0** · 最后更新：2026-03-08

Shannon-LangGraph 是一个基于 **LangGraph + FastAPI** 的研究型数据集生成与多智能体编排平台。系统将复杂用户请求自动拆解为可追踪的任务 DAG，通过 LLM Agent 与工具链（Web 搜索、网页抓取、向量记忆）并行执行，并以实时事件流驱动前端调用链可视化。

---

## 目录

- [系统架构](#系统架构)
- [核心工作流](#核心工作流)
- [目录结构](#目录结构)
- [快速启动](#快速启动)
- [Docker 一键部署](#docker-一键部署)
- [API 参考](#api-参考)
- [Workflow 模板系统](#workflow-模板系统)
- [配置系统](#配置系统)
- [模型与策略](#模型与策略)
- [质量控制](#质量控制)
- [Web 调试前端](#web-调试前端)
- [测试](#测试)
- [环境变量速查](#环境变量速查)
- [文档索引](#文档索引)

---

## 系统架构

项目采用**三层微服务**架构，各层独立部署、独立扩缩：

```
┌───────────────────────────────────────────────────────────────┐
│               Desktop / Debug Console (Next.js)               │
│         实时调用链可视化 · Chat 交互 · 运行状态监控            │
└──────────────────────────┬────────────────────────────────────┘
                           │  HTTP / SSE
┌──────────────────────────┴────────────────────────────────────┐
│          编排层 — Orchestration (FastAPI + LangGraph)          │
│  6 节点状态机 · Checkpoint 持久化 · 异步任务注册 · 事件流推送  │
│  端口 :8000                                                    │
└──────────┬──────────────────────────────────┬─────────────────┘
           │  HTTP                            │
  ┌────────┴───────────────┐     ┌────────────┴────────────────┐
  │  LLM Service (FastAPI) │     │     存储层 Storage           │
  │  端口 :8001            │     │  Redis  — 会话 / 事件流     │
  │  · 模型分级调度        │     │  Postgres — 状态 / 日志     │
  │  · Web 搜索 (Tavily)   │     │  Qdrant — 向量记忆         │
  │  · 网页抓取 & 爬虫     │     │  SQLite — LangGraph        │
  │  · 向量记忆读写        │     │          Checkpoint         │
  │  · 预算 & 质量控制     │     │                             │
  └────────────────────────┘     └─────────────────────────────┘
```

| 组件 | 技术栈 | 职责 |
|------|--------|------|
| **编排层** | FastAPI + LangGraph + SQLite Checkpoint | 工作流状态机、任务调度、SSE 事件推送、线程安全运行注册表 |
| **LLM Service** | FastAPI + OpenAI SDK + Tavily | 模型调用、工具执行、检索管线、预算与质量控制 |
| **存储层** | Redis 7 / PostgreSQL 16 / Qdrant | 会话管理、状态持久化、事件日志、向量语义搜索 |
| **前端** | Next.js 14 + React 18 + @xyflow/react | 实时 Graph 可视化、Chat 提交、Run 状态追踪 |

---

## 核心工作流

Shannon 的 LangGraph 状态机包含 **6 个节点**，按顺序执行：

```
refine ──▸ decompose ──▸ schedule ──▸ execute ──▸ verify ──▸ finalize
 意图理解     任务分解     DAG 调度     并行执行     质量验证     汇总输出
```

| 阶段 | 节点 | 调用端点 | 模型层级 | 说明 |
|------|------|----------|----------|------|
| 1 | **refine** | `/agent/refine` | 按策略选择 | 解析用户意图，输出 `query_type`、`research_areas`、`complexity` |
| 2 | **decompose** | `/agent/decompose` | small（控制成本） | 拆解为带依赖关系的任务列表（TaskContract） |
| 3 | **schedule** | 本地逻辑 | — | 拓扑排序构建 DAG、检测循环依赖、生成就绪队列 |
| 4 | **execute** | `/agent/run` × N | 按 task 指定 | 并行执行就绪任务，支持搜索→抓取→生成多轮迭代 |
| 5 | **verify** | 本地逻辑 | — | 校验 acceptance_criteria，不合格触发重试 |
| 6 | **finalize** | `/v1/responses` | large（保质量） | 综合全部 task_results 生产最终输出 |

每个阶段发出 `NODE_STARTED` / `NODE_COMPLETED` / `NODE_FAILED` 事件，前端实时渲染阶段进度条。

---

## 目录结构

```
Shannon/
├── src/shannon/
│   ├── orchestration/          # 编排层
│   │   ├── main.py             #   uvicorn 入口
│   │   └── orchestrator/
│   │       ├── app.py          #   FastAPI 路由 + 启动逻辑
│   │       ├── graph.py        #   LangGraph 6 节点状态机
│   │       ├── state.py        #   ResearchState / ResearchTask 定义
│   │       └── llm_service_client.py  # → LLM Service HTTP 客户端
│   ├── llm_service/            # LLM 服务层
│   │   ├── main.py             #   FastAPI 路由 + Agent 端点
│   │   ├── provider_manager.py #   模型分级调度 (small/medium/large)
│   │   ├── presets.py          #   角色预设 (system prompt)
│   │   ├── prompts/            #   提示词模板
│   │   ├── retrieval/          #   检索管线 (search/fetch/crawl/selector)
│   │   ├── tool_calling/       #   工具执行器
│   │   └── budget/             #   Token 预算追踪
│   ├── storage/                # 存储层
│   │   ├── postgres/           #   PostgreSQL 客户端 + 自动迁移
│   │   ├── redis/              #   Session Manager + Streaming Manager
│   │   └── qdrant/             #   向量存储客户端
│   └── utils/                  # 公共工具
├── config/
│   ├── app.yaml                # 全局配置（超时、重试、默认模型）
│   ├── llm.yaml                # 模型列表（context_window、temperature）
│   ├── models.yaml             # 模型分级映射（tier → provider → model）
│   ├── tools.yaml              # 工具配置（Tavily、MCP）
│   ├── validation/             # 预算规则 + 质量规则 + JSON Schema
│   ├── vector_db/              # Qdrant 初始化配置
│   └── workflows/examples/     # 工作流 YAML 模板（7 个示例）
├── desktop/                    # Next.js 调试前端
│   ├── app/                    #   页面 + API 路由代理
│   ├── components/             #   Chat / Graph / RunStatus 组件
│   ├── hooks/                  #   useChatThread / useEventStream / useRunController
│   ├── lib/                    #   API Client / 事件 Reducer / 类型定义
│   └── tests/                  #   Unit / Component / E2E 测试
├── tests/                      # 后端测试
│   ├── unit/                   #   7 个单元测试模块
│   ├── integration/            #   LLM Service 集成测试
│   └── e2e/                    #   端到端测试
├── migrations/
│   ├── postgres/               #   SQL 迁移脚本（3 个版本）
│   └── qdrant/                 #   Collection 初始化脚本
├── deploy/
│   ├── docker/                 #   Dockerfile × 2
│   └── scripts/                #   部署引导脚本
├── docs/                       # 项目文档（8 篇）
├── docker-compose.yml          # 5 服务编排
├── Makefile                    # 常用命令
├── pyproject.toml              # Python 项目元数据
└── requirements.txt            # Python 依赖
```

---

## 快速启动

### 前置条件

- Python ≥ 3.11（推荐使用 conda）
- Node.js ≥ 18（前端调试可选）
- 运行中的 Redis、PostgreSQL、Qdrant 实例（或使用 Docker Compose）
- OpenAI API Key

### 本地开发模式

```bash
# 1. 初始化环境变量
make init
# 编辑 .env，填入 OPENAI_API_KEY 等

# 2. 安装 Python 依赖
make install

# 3. 启动编排层（终端 1）
make run-orchestration    # → http://127.0.0.1:8000

# 4. 启动 LLM Service（终端 2）
make run-llm              # → http://127.0.0.1:8001

# 5. 验证服务状态
curl http://127.0.0.1:8000/healthz
# 预期: {"status":"ok","pg_available":true}
```

### 提交第一个工作流

```bash
curl -X POST http://127.0.0.1:8000/runs \
  -H "Content-Type: application/json" \
  -d '{
    "thread_id": "my-first-run",
    "user_request": "对比分析 GPT-5 和 Claude-4 的技术特点",
    "strategy": "standard"
  }'
# 预期: 202 Accepted → {"thread_id":"my-first-run","status":"accepted"}
```

```bash
# 查询运行状态
curl http://127.0.0.1:8000/threads/my-first-run/run_status
# 预期: {"thread_id":"my-first-run","run_status":"running|completed|failed","error":null}
```

---

## Docker 一键部署

```bash
# 启动全部 5 个服务
docker-compose up -d

# 服务列表：
#   orchestration  :8000   编排层
#   llm_service    :8001   LLM 服务
#   redis          :6379   会话与事件流
#   postgres       :5432   状态持久化
#   qdrant         :6333   向量存储
```

> Docker Compose 已内置 PostgreSQL 健康检查（`pg_isready`），编排层会等待 Postgres 完全就绪后再启动，避免启动时序导致的持久化降级问题。

```bash
# 健康检查
curl http://127.0.0.1:8000/healthz
docker-compose ps

# 查看日志
docker-compose logs -f orchestration
docker-compose logs -f llm_service
```

---

## API 参考

### 编排层（:8000）

| 端点 | 方法 | 说明 | 响应 |
|------|------|------|------|
| `/healthz` | GET | 健康检查 + PG 状态 | `{"status":"ok","pg_available":true}` |
| `/workflows/templates` | GET | 列出所有可用模板 | `{"templates":[...]}` |
| `/workflows/templates/{name}` | GET | 查看模板详情（支持 `extends` 继承合并） | `{"template":{...}}` |
| `/runs` | POST | 提交工作流（异步，后台线程执行） | **202** `{"thread_id":"...","status":"accepted"}` |
| `/threads/{id}/run_status` | GET | 查询运行状态 | `{"run_status":"running\|completed\|failed"}` |
| `/threads/{id}/state_db` | GET | 查询 PG 中的持久化状态 | `{"thread_id":"...","state":{...}\|null}` |

**POST /runs 请求体**：
```json
{
  "thread_id": "unique-id",
  "user_request": "你的研究问题",
  "strategy": "quick | standard | deep",
  "workflow_template": "模板名（可选）",
  "workflow_context": { "自定义上下文": "..." },
  "strict_output": false,
  "quality_mode": "best_effort | strict"
}
```

> 同一 `thread_id` 重复提交会返回 **409 Conflict**。

### LLM Service（:8001）

| 端点 | 方法 | 说明 |
|------|------|------|
| `/agent/refine` | POST | 意图理解与查询规范化 |
| `/agent/decompose` | POST | 任务分解，生成带依赖的 TaskContract 列表 |
| `/agent/run` | POST | 执行单个任务（含搜索 → 抓取 → 生成多轮迭代） |
| `/v1/responses` | POST | 多任务结果综合汇总 |
| `/v1/search` | POST | Web 搜索（Tavily API） |
| `/v1/fetch` | POST | 抓取指定 URL 内容 |
| `/v1/crawl` | POST | 多页爬虫 |
| `/v1/memory/upsert` | POST | 写入向量记忆（Qdrant） |
| `/v1/memory/search` | POST | 向量语义搜索 |
| `/v1/tool_call` | POST | 按名称执行工具 |

详见 `docs/api_reference.md`。

---

## Workflow 模板系统

内置 7 个示例模板于 `config/workflows/examples/`，支持通过 YAML 定义复杂工作流：

### 模板能力

| 特性 | 说明 |
|------|------|
| **继承** | `extends: [parent_template]`，子模板覆盖父模板字段 |
| **节点类型** | `simple` / `dag`（并行子任务） / `cognitive` / `custom` |
| **执行策略** | `react` / `reflection` / `chain_of_thought` |
| **依赖管理** | `depends_on: [node_id, ...]`，自动拓扑排序 |
| **错误处理** | `on_fail: { degrade_to: chain_of_thought, retry: 1 }` |
| **预算控制** | 每节点独立 `budget_agent_max` Token 限额 |

### 使用示例

```bash
# 1. 列出所有模板
curl -s http://127.0.0.1:8000/workflows/templates

# 2. 查看模板详情（extends 会自动合并）
curl -s http://127.0.0.1:8000/workflows/templates/market_analysis_playbook

# 3. 使用模板运行
curl -s -X POST http://127.0.0.1:8000/runs \
  -H "Content-Type: application/json" \
  -d '{
    "thread_id": "wf-demo-1",
    "workflow_template": "parallel_items_example",
    "user_request": "生成本周技术快报",
    "workflow_context": {
      "topics": ["AI", "Cybersecurity", "Robotics"],
      "depth": "brief"
    }
  }'
```

### 内置模板一览

| 模板名 | 描述 |
|--------|------|
| `simple_analysis` | 单步分析 |
| `market_analysis` | 市场分析基础流程 |
| `market_analysis_playbook` | 市场分析进阶（继承 market_analysis + 合规审查） |
| `research_summary` | 研究总结 |
| `research_summary_enterprise` | 企业级研究总结 |
| `parallel_dag_example` | 并行 DAG 示例（数据采集 → 定量/定性分析 → 交叉验证） |
| `parallel_items_example` | 并行条目处理示例 |
| `complex_dag` | 复杂 DAG 编排示例 |

---

## 配置系统

所有配置文件位于 `config/` 目录：

| 文件 | 用途 | 关键配置 |
|------|------|----------|
| `app.yaml` | 全局设置 | `thread_timeout_sec: 1800`、`max_retry: 3`、`default_model: gpt-5-mini` |
| `llm.yaml` | 模型参数 | 各模型的 `context_window`、`temperature` |
| `models.yaml` | 模型分级 | `small → gpt-5-nano`、`medium → gpt-5-mini`、`large → gpt-5.1` |
| `tools.yaml` | 工具开关 | Tavily 搜索配置、MCP 超时与限流 |
| `validation/budget_rules.yaml` | 预算规则 | `max_token: 8000`、`max_retry: 3` |
| `validation/quality_rules.yaml` | 质量规则 | `min_content_length: 50`、`required_keywords` |
| `validation/spec_schema.json` | 输入校验 | JSON Schema 约束 |

---

## 模型与策略

### 三级模型分层

| 层级 | 模型 | 使用场景 | 设计意图 |
|------|------|----------|----------|
| **small** | gpt-5-nano | decompose（任务分解） | 极致控制成本 |
| **medium** | gpt-5-mini | refine（意图理解）、通用任务 | 成本与质量均衡 |
| **large** | gpt-5.1 | finalize（最终汇总）、复杂深度任务 | 保证输出质量 |

### 三种执行策略

| 策略 | 说明 | 适用场景 |
|------|------|----------|
| `quick` | 最少任务、快速完成 | 简单查询、快速验证 |
| `standard` | 标准深度、适中任务数 | 日常研究、报告生成 |
| `deep` | 最大深度、多轮迭代 | 深度分析、数据集生成 |

### 超时配置全景

| 环节 | 配置项 | 默认值 |
|------|--------|--------|
| OpenAI SDK 客户端级 | `OPENAI_TIMEOUT_SECONDS` | 120s |
| `/agent/run` (large) | `_run_request_timeout()` | 180s |
| `/v1/responses` (large) | `_responses_request_timeout()` | 240s |
| 编排层 → LLM Service | `ORCH_LLM_SERVICE_TIMEOUT_SECONDS` | 120s |
| 编排层 → responses | `ORCH_LLM_SERVICE_TIMEOUT_RESPONSES_SECONDS` | 300s |

---

## 质量控制

v0.3.0 引入两个质量控制参数，精细管控 LLM 输出行为：

### `strict_output`（默认 `false`）

| 值 | 行为 |
|----|------|
| `false` | 纯转换任务（如 JSONL 格式化）可走确定性 fallback 短路，跳过 LLM 调用 |
| `true` | **强制所有任务经过 LLM 实质生成**，禁用模板化 fallback |

### `quality_mode`（默认 `"best_effort"`）

| 值 | 行为 |
|----|------|
| `best_effort` | 低价值内容降级为 fallback 模板，标记 `quality_status: "degraded"` |
| `strict` | 低价值内容保持 `error` 状态，触发编排层重试 |

```bash
# 示例：强制 LLM 生成 + 严格质量
curl -X POST http://127.0.0.1:8000/runs \
  -H "Content-Type: application/json" \
  -d '{
    "user_request": "生成深度分析报告",
    "strategy": "deep",
    "strict_output": true,
    "quality_mode": "strict"
  }'
```

---

## Web 调试前端

`desktop/` 目录中提供了一个 **Shannon Debug Console**，基于 Next.js + React + @xyflow/react 构建，用于实时监控工作流执行。

### 功能特性

- **Chat 交互**：通过对话框提交研究请求
- **实时 Graph 调用链**：可视化 Agent 调用关系（基于 @xyflow/react）
- **6 阶段进度条**：实时显示 refine → decompose → schedule → execute → verify → finalize 各阶段状态（running / completed / failed）
- **Run 状态追踪**：通过 SSE 实时接收 `NODE_STARTED` / `AGENT_CALL_*` / `WORKFLOW_COMPLETED` 事件
- **Node 详情面板**：点击节点查看任务参数、model_tier、返回内容

### 启动前端

```bash
cd desktop
cp -n .env.example .env.local   # 配置后端地址
npm install
npm run dev                     # → http://localhost:3000
```

> `start-dev.sh` 脚本会自动释放占用的 3000 端口，避免 `EADDRINUSE` 冲突。

### 前端技术栈

| 依赖 | 版本 | 用途 |
|------|------|------|
| Next.js | 14.2 | React 全栈框架 |
| React | 18.3 | UI 组件 |
| @xyflow/react | 12.8 | Graph 可视化 |
| TypeScript | 5.7 | 类型安全 |
| Vitest | 2.1 | 单元 / 组件测试 |
| Playwright | 1.52 | E2E 测试 |

---

## 测试

### 后端测试（pytest）

```bash
make test                # 运行全部后端测试（42 个用例）
```

| 测试模块 | 覆盖范围 |
|----------|----------|
| `test_llm_service_main.py` | LLM Service 端点、transform 判定、DAG 深度验证 |
| `test_provider_manager.py` | 模型分级调度 |
| `test_retrieval_pipeline.py` | 搜索 → 抓取 → 候选排序管线 |
| `test_research_orchestrator.py` | LangGraph 状态机执行流 |
| `test_workflow_templates.py` | YAML 模板加载与继承 |
| `test_data_layer.py` | 存储层读写 |
| `test_orchestrator_llm_service_client.py` | 编排层 ↔ LLM Service 通信 |

### 前端测试

```bash
cd desktop
npm run test:unit        # Vitest 单元测试
npm run test:component   # Vitest 组件测试
npm run test:e2e         # Playwright E2E 测试
npm test                 # 运行全部
```

---

## 环境变量速查

```bash
# ── 必要配置 ──
OPENAI_API_KEY=sk-xxx

# ── 数据层 ──
POSTGRES_DSN=postgresql://postgres:postgres@localhost:5432/shannon
REDIS_URL=redis://localhost:6379/0
QDRANT_URL=http://localhost:6333
POSTGRES_AUTO_MIGRATE=true          # 启动时自动执行 SQL 迁移
ENABLE_VECTOR_MEMORY=true           # 启用向量记忆

# ── 超时配置 ──
OPENAI_TIMEOUT_SECONDS=120                          # SDK 客户端级超时
# OPENAI_RUN_TIMEOUT_SECONDS=180                    # /agent/run 覆盖（默认按 tier 自动）
# OPENAI_RESPONSES_TIMEOUT_SECONDS=240              # /v1/responses 覆盖

# ── 编排层 → LLM Service ──
LLM_SERVICE_BASE_URL=http://127.0.0.1:8001          # 本地开发
# LLM_SERVICE_BASE_URL=http://llm_service:8001      # Docker 网络
ORCH_LLM_SERVICE_TIMEOUT_SECONDS=120                # 通用请求超时
ORCH_LLM_SERVICE_TIMEOUT_RESPONSES_SECONDS=300      # /v1/responses 超时
ORCH_LLM_SERVICE_RETRIES=2                          # 重试次数

# ── Redis Session ──
SESSION_TTL_SECONDS=2592000         # 30 天
SESSION_MAX_HISTORY=500
SESSION_CACHE_SIZE=1000
```

---

## 文档索引

| 文档 | 说明 |
|------|------|
| [docs/architecture.md](docs/architecture.md) | 架构设计详解 |
| [docs/quickstart.md](docs/quickstart.md) | 快速入门指南 |
| [docs/api_reference.md](docs/api_reference.md) | 完整 API 文档 |
| [docs/langgraph_workflow.md](docs/langgraph_workflow.md) | LangGraph 工作流详解 |
| [docs/checkpoint_guide.md](docs/checkpoint_guide.md) | Checkpoint 持久化指南 |
| [docs/validation_rules.md](docs/validation_rules.md) | 验证规则说明 |
| [docs/troubleshooting.md](docs/troubleshooting.md) | 故障排查手册（9 个已知 Issue） |
| [docs/backend_changelog.md](docs/backend_changelog.md) | 后端修改历史记录 |

---

## License

见 [LICENSE](LICENSE)。
