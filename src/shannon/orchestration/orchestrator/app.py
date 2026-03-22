from __future__ import annotations

import asyncio
import json
import logging
import os
import queue
import threading
from typing import Any, Dict

from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import StreamingResponse
from langgraph.checkpoint.memory import MemorySaver
from langgraph.checkpoint.sqlite import SqliteSaver

from shannon.orchestration.orchestrator.graph import (
    build_graph,
    list_checkpoints,
    restore_checkpoint,
    set_streaming_manager,
)
from shannon.orchestration.orchestrator.gatekeeper import phase_gatekeeper
from shannon.orchestration.workflows import (
    WorkflowTemplateError,
    compile_workflow_template,
    list_workflow_templates,
    load_workflow_template,
)
from shannon.storage.memory_layer import shared_memory_store
from shannon.storage.postgres.client import pg_client
from shannon.storage.redis.session_manager import session_manager
from shannon.storage.redis.streaming_manager import Event, streaming_manager
from shannon.storage.version_layer import git_version_store
from shannon.utils.logger import setup_logging

logger = logging.getLogger(__name__)

# 中文注释：编排层 FastAPI 应用（LangGraph + Checkpoint）
app = FastAPI(title="Shannon Orchestrator", version="0.3.0")

# 中文注释：SQLite Checkpointer 的上下文管理器
_sqlite_cm = None

# 中文注释：后台运行注册表 — 追踪每个 thread_id 的执行状态
# key=thread_id, value={"status": "running"|"completed"|"failed", "error": str|None}
_run_registry: Dict[str, Dict[str, Any]] = {}
_run_registry_lock = threading.Lock()


# 中文注释：函数 _create_checkpointer 的入口

def _create_checkpointer():
    # 中文注释：优先使用 SQLite 持久化，否则回退内存模式
    path = os.getenv("CHECKPOINT_PATH")
    if path:
        cm = SqliteSaver.from_conn_string(path)
        saver = cm.__enter__()
        return saver, cm
    return MemorySaver(), None


# 中文注释：函数 _init_runtime 的入口

def _init_runtime() -> None:
    # 中文注释：初始化日志与 checkpointer/graph
    setup_logging()
    # 中文注释：初始化 PostgreSQL（自动迁移可通过环境变量关闭）
    if str(os.getenv("POSTGRES_AUTO_MIGRATE", "true")).lower() in {"1", "true", "yes", "on"}:
        try:
            pg_client.run_migrations()
        except Exception:
            # 中文注释：迁移失败不阻断主流程，保留降级能力
            pass

    checkpointer, cm = _create_checkpointer()
    app.state.checkpointer = checkpointer
    app.state.graph = build_graph(checkpointer)
    app.state._sqlite_cm = cm
    app.state.pg_client = pg_client
    app.state.session_manager = session_manager
    app.state.streaming_manager = streaming_manager
    app.state.shared_memory_store = shared_memory_store
    set_streaming_manager(streaming_manager)


# 中文注释：函数 _shutdown_runtime 的入口

def _shutdown_runtime() -> None:
    # 中文注释：关闭 SQLite 连接
    set_streaming_manager(None)
    cm = getattr(app.state, "_sqlite_cm", None)
    if cm is not None:
        cm.__exit__(None, None, None)


# 中文注释：服务启动时初始化
@app.on_event("startup")
def on_startup() -> None:
    _init_runtime()


# 中文注释：服务关闭时清理资源
@app.on_event("shutdown")
def on_shutdown() -> None:
    _shutdown_runtime()


# 中文注释：健康检查
@app.get("/healthz")
def healthz():
    _pg = getattr(app.state, "pg_client", None)
    return {
        "status": "ok",
        "pg_available": _pg.available if _pg else False,
    }


# 中文注释：列出可用模板工作流
@app.get("/workflows/templates")
def workflow_templates():
    return {"templates": list_workflow_templates()}


# 中文注释：查看模板工作流详情（含继承合并）
@app.get("/workflows/templates/{template_name}")
def workflow_template(template_name: str):
    try:
        template = load_workflow_template(template_name)
        return {"template": template}
    except WorkflowTemplateError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


# 中文注释：运行一次完整研究流程（异步：立即返回 202，后台执行 graph.invoke）
@app.post("/runs", status_code=202)
def run(req: Dict[str, Any]):
    thread_id = str(req.get("thread_id") or "demo-thread")
    phase = str(req.get("phase") or "phase-1").lower().strip()

    gate_check = phase_gatekeeper.can_enter(run_id=thread_id, phase=phase)
    if not bool(gate_check.get("allowed")):
        with _run_registry_lock:
            _run_registry[thread_id] = {"status": "frozen", "error": str(gate_check.get("reason") or "gate blocked")}
        raise HTTPException(status_code=409, detail=f"phase gate blocked: {gate_check.get('reason')}")

    # 中文注释：检查该 thread 是否已有正在执行的 run，防止重复提交
    with _run_registry_lock:
        existing = _run_registry.get(thread_id)
        if existing and existing["status"] == "running":
            raise HTTPException(status_code=409, detail=f"thread {thread_id} 已有运行中的工作流")

    workflow_template_ref = str(req.get("workflow_template") or req.get("template") or "").strip()
    workflow_context = req.get("workflow_context") or req.get("context") or {}
    if workflow_context is None:
        workflow_context = {}
    if not isinstance(workflow_context, dict):
        raise HTTPException(status_code=400, detail="workflow_context 必须是对象")

    user_request = str(req.get("user_request") or "").strip()
    if not user_request and workflow_template_ref:
        user_request = f"Execute workflow template: {workflow_template_ref}"
    if not user_request:
        raise HTTPException(status_code=400, detail="user_request 不能为空")

    user_id = str(req.get("user_id") or "anonymous")
    tenant_id = str(req.get("tenant_id") or "")

    compiled_template: Dict[str, Any] | None = None
    if workflow_template_ref:
        try:
            template = load_workflow_template(workflow_template_ref)
            compiled_template = compile_workflow_template(
                template=template,
                user_request=user_request,
                context=workflow_context,
            )
        except WorkflowTemplateError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc

    # 中文注释：开发阶段优先观察真实 decompose 行为，默认放宽等待；可由请求或环境变量覆盖
    env_decompose_timeout = os.getenv("ORCH_DECOMPOSE_TIMEOUT_SECONDS", "120")
    env_decompose_retries = os.getenv("ORCH_DECOMPOSE_HTTP_RETRIES", "1")
    try:
        default_decompose_timeout = max(15.0, min(float(env_decompose_timeout), 600.0))
    except Exception:  # noqa: BLE001
        default_decompose_timeout = 120.0
    try:
        default_decompose_retries = max(0, min(int(env_decompose_retries), 5))
    except Exception:  # noqa: BLE001
        default_decompose_retries = 1

    req_decompose_timeout = req.get("decompose_timeout_seconds")
    req_decompose_retries = req.get("decompose_http_retries")
    try:
        decompose_timeout_seconds = (
            max(15.0, min(float(req_decompose_timeout), 600.0))
            if req_decompose_timeout is not None
            else default_decompose_timeout
        )
    except Exception:  # noqa: BLE001
        decompose_timeout_seconds = default_decompose_timeout
    try:
        decompose_http_retries = (
            max(0, min(int(req_decompose_retries), 5))
            if req_decompose_retries is not None
            else default_decompose_retries
        )
    except Exception:  # noqa: BLE001
        decompose_http_retries = default_decompose_retries

    raw_strategy = str(req.get("strategy") or "deep").strip().lower()
    strategy = "deep"
    strategy_alias_deprecated = raw_strategy in {"quick", "standard"}
    if strategy_alias_deprecated:
        logger.warning("deprecated strategy alias received: %s -> %s", raw_strategy, strategy)

    state_in = {
        "thread_id": thread_id,
        "phase": phase,
        "gate_status": str(gate_check.get("gate_status") or "open"),
        "user_request": user_request,
        "strategy": strategy,
        "strategy_requested": raw_strategy,
        "strategy_alias_deprecated": strategy_alias_deprecated,
        # 中文注释：并发上限、任务上限可由调用方覆盖
        "max_concurrency": int(req.get("max_concurrency", 3) or 3),
        "max_tasks": int(req.get("max_tasks", 6) or 6),
        # 中文注释：质量控制参数，传透至 LLM Service
        "strict_output": bool(req.get("strict_output", False)),
        "quality_mode": str(req.get("quality_mode", "best_effort") or "best_effort"),
        # 中文注释：decompose 阶段的 HTTP 等待与重试策略（开发阶段默认更宽松）
        "decompose_timeout_seconds": decompose_timeout_seconds,
        "decompose_http_retries": decompose_http_retries,
        # 中文注释：默认对接本地 llm-service，可通过请求或环境变量覆盖
        "llm_service_base_url": req.get("llm_service_base_url")
        or os.getenv("LLM_SERVICE_BASE_URL", "http://127.0.0.1:8001"),
    }
    if compiled_template is not None:
        state_in.update(
            {
                "workflow_template_name": compiled_template.get("name"),
                "workflow_template_path": compiled_template.get("template_path"),
                "workflow_context": workflow_context,
                "template_tasks": compiled_template.get("tasks", []),
                "budget": compiled_template.get("budget", {}),
                "max_tasks": max(
                    int(state_in.get("max_tasks", 6) or 6),
                    len(compiled_template.get("tasks", [])),
                ),
            }
        )

    # 中文注释：会话连续性：按 thread_id 固定 session_id（可多轮复用）
    session = app.state.session_manager.get_session(thread_id)
    if session is None:
        session = app.state.session_manager.create_session(
            session_id=thread_id,
            user_id=user_id,
            tenant_id=tenant_id,
            metadata={"source": "orchestrator"},
        )
    app.state.session_manager.add_message(
        session_id=thread_id,
        role="user",
        content=user_request,
        metadata={
            "strategy": state_in["strategy"],
            "strategy_requested": state_in.get("strategy_requested"),
            "strategy_alias_deprecated": bool(state_in.get("strategy_alias_deprecated")),
        },
    )

    # 中文注释：初始化 run 目录清单，定义 reports/<run_id>/ 结构
    try:
        app.state.shared_memory_store.ensure_run_manifest(
            run_id=thread_id,
            manifest={
                "phase": state_in.get("phase"),
                "gate_status": state_in.get("gate_status"),
                "strategy": state_in.get("strategy"),
                "strategy_requested": state_in.get("strategy_requested"),
                "strategy_alias_deprecated": bool(state_in.get("strategy_alias_deprecated")),
                "user_id": user_id,
                "tenant_id": tenant_id,
            },
        )
    except Exception:
        pass

    # 中文注释：发布工作流开始事件
    app.state.streaming_manager.publish(
        thread_id,
        Event(
            workflow_id=thread_id,
            type="WORKFLOW_STARTED",
            agent_id="orchestrator",
            message="workflow started",
            payload={
                "strategy": state_in["strategy"],
                "strategy_requested": state_in.get("strategy_requested"),
                "strategy_alias_deprecated": bool(state_in.get("strategy_alias_deprecated")),
                "run_id": thread_id,
                "phase": state_in.get("phase"),
                "gate_status": state_in.get("gate_status"),
            },
        ),
    )

    # 中文注释：注册后台运行并启动后台线程
    with _run_registry_lock:
        _run_registry[thread_id] = {"status": "running", "error": None}

    def _background_run() -> None:
        """在后台线程中执行 graph.invoke，完成后更新注册表和持久化层。"""
        try:
            out = app.state.graph.invoke(state_in, config={"configurable": {"thread_id": thread_id}})

            # 中文注释：写入会话上下文与消息
            app.state.session_manager.update_context(thread_id, "last_state", out)
            app.state.session_manager.add_message(
                session_id=thread_id,
                role="assistant",
                content=str((out.get("final_output") or {}).get("summary") or "workflow completed"),
                metadata={"status": "completed"},
            )

            # 中文注释：长期状态落库（PostgreSQL）
            app.state.pg_client.save_thread_state(thread_id, out, status="completed")

            # 中文注释：发布完成事件
            app.state.streaming_manager.publish(
                thread_id,
                Event(
                    workflow_id=thread_id,
                    type="WORKFLOW_COMPLETED",
                    agent_id="orchestrator",
                    message="workflow completed",
                    payload={
                        "done": bool(out.get("done")),
                        "error_count": len(out.get("errors", [])),
                        "run_id": thread_id,
                        "phase": state_in.get("phase"),
                        "gate_status": state_in.get("gate_status"),
                    },
                ),
            )
            with _run_registry_lock:
                _run_registry[thread_id] = {"status": "completed", "error": None}
            logger.info("workflow %s completed", thread_id)
        except Exception as exc:  # noqa: BLE001
            fail_payload = {"error": f"{type(exc).__name__}: {str(exc)}"}
            app.state.pg_client.save_thread_state(thread_id, {"error": fail_payload["error"]}, status="failed")
            app.state.streaming_manager.publish(
                thread_id,
                Event(
                    workflow_id=thread_id,
                    type="WORKFLOW_FAILED",
                    agent_id="orchestrator",
                    message="workflow failed",
                    payload={
                        **fail_payload,
                        "run_id": thread_id,
                        "phase": state_in.get("phase"),
                        "gate_status": state_in.get("gate_status"),
                    },
                ),
            )
            with _run_registry_lock:
                _run_registry[thread_id] = {"status": "failed", "error": fail_payload["error"]}
            logger.exception("workflow %s failed", thread_id)

    thread = threading.Thread(target=_background_run, name=f"run-{thread_id}", daemon=True)
    thread.start()

    # 中文注释：立即返回 202 Accepted，前端通过 SSE/polling 获取进度
    return {"thread_id": thread_id, "status": "accepted"}


# 中文注释：查询某线程的后台运行状态
@app.get("/threads/{thread_id}/run_status")
def run_status(thread_id: str):
    with _run_registry_lock:
        entry = _run_registry.get(thread_id)
    if entry is None:
        return {"thread_id": thread_id, "run_status": "unknown"}
    return {"thread_id": thread_id, "run_status": entry["status"], "error": entry.get("error")}


# 中文注释：查询某线程的 checkpoint 列表
@app.get("/threads/{thread_id}/checkpoints")
def checkpoints(thread_id: str):
    return {"thread_id": thread_id, "checkpoints": list_checkpoints(app.state.graph, thread_id)}


# 中文注释：恢复到指定 checkpoint（time travel）
@app.post("/threads/{thread_id}/restore")
def restore(thread_id: str, payload: Dict[str, Any]):
    checkpoint_id = payload.get("checkpoint_id")
    if not checkpoint_id:
        raise HTTPException(status_code=400, detail="checkpoint_id 不能为空")
    state = restore_checkpoint(app.state.graph, thread_id, str(checkpoint_id))
    return {"thread_id": thread_id, "state": state}


# 中文注释：查看当前状态
@app.get("/threads/{thread_id}/state")
def current_state(thread_id: str):
    config = {"configurable": {"thread_id": thread_id}}
    snapshot = app.state.graph.get_state(config)
    return {"thread_id": thread_id, "state": snapshot.values}


# 中文注释：查看线程会话（Redis + 本地回退）
@app.get("/threads/{thread_id}/session")
def thread_session(thread_id: str):
    session = app.state.session_manager.get_session(thread_id)
    if session is None:
        raise HTTPException(status_code=404, detail="session 不存在")
    return {"thread_id": thread_id, "session": session.to_dict()}


# 中文注释：查看线程事件流回放（Redis Stream + 内存回退）
@app.get("/threads/{thread_id}/events")
def thread_events(thread_id: str, since_seq: int = 0, limit: int = 200):
    events = app.state.streaming_manager.replay_since(thread_id, since_seq=since_seq, limit=limit)
    return {"thread_id": thread_id, "events": [event.to_dict() for event in events]}


# 中文注释：SSE 订阅线程事件（先回放再实时推送）
@app.get("/threads/{thread_id}/events/stream")
async def thread_events_stream(request: Request, thread_id: str, since_seq: int = 0):
    channel = app.state.streaming_manager.subscribe(thread_id, buffer=512)
    backlog = app.state.streaming_manager.replay_since(thread_id, since_seq=since_seq, limit=200)

    async def event_stream():
        try:
            # 中文注释：先发送历史事件，保证前端首次连接可补齐进度
            for item in backlog:
                yield f"data: {json.dumps(item.to_dict(), ensure_ascii=False)}\n\n"

            # 中文注释：持续推送实时事件，空闲时发送心跳避免连接被中间层断开
            while True:
                if await request.is_disconnected():
                    break
                try:
                    item = await asyncio.to_thread(channel.get, True, 1.0)
                    yield f"data: {json.dumps(item.to_dict(), ensure_ascii=False)}\n\n"
                except queue.Empty:
                    yield ": keepalive\n\n"
        finally:
            app.state.streaming_manager.unsubscribe(thread_id, channel)

    return StreamingResponse(
        event_stream(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )


# 中文注释：查看线程在 PostgreSQL 的最新状态快照
@app.get("/threads/{thread_id}/state_db")
def current_state_db(thread_id: str):
    state_row = app.state.pg_client.get_thread_state(thread_id)
    if state_row is None:
        # 中文注释：工作流执行期间 PG 可能尚无数据，返回空而非 404，减少日志噪音
        return {"thread_id": thread_id, "state": None}
    return {"thread_id": thread_id, "state": state_row}


# 中文注释：阶段门禁决策（passed/warning/failed）
@app.post("/threads/{thread_id}/phases/{phase}/gate")
def phase_gate_decision(thread_id: str, phase: str, req: Dict[str, Any]):
    status = str(req.get("status") or "").strip().lower()
    reason = str(req.get("reason") or "").strip()
    if not reason:
        raise HTTPException(status_code=400, detail="reason 不能为空")
    try:
        payload = phase_gatekeeper.record_decision(
            run_id=thread_id,
            phase=str(phase).lower().strip(),
            status=status,
            reason=reason,
            metadata=req.get("metadata") if isinstance(req.get("metadata"), dict) else None,
        )
        if status == "passed":
            tag_result = git_version_store.create_stage_tag(thread_id, str(phase).lower().strip())
            git_version_store.append_log(
                run_id=thread_id,
                payload={
                    "type": "stage_tag",
                    "phase": str(phase).lower().strip(),
                    "result": tag_result,
                },
            )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except RuntimeError as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc
    return {"ok": True, "gate": payload}


# 中文注释：查询阶段是否可进入
@app.get("/threads/{thread_id}/phases/{phase}/gate")
def phase_gate_check(thread_id: str, phase: str):
    try:
        payload = phase_gatekeeper.can_enter(run_id=thread_id, phase=str(phase).lower().strip())
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return {"thread_id": thread_id, "phase": str(phase).lower().strip(), **payload}


# 中文注释：append-only 守卫检查（禁止 rebase/merge）
@app.post("/version/guard/check")
def version_guard_check(req: Dict[str, Any]):
    operation = str(req.get("operation") or "").strip().lower()
    if not operation:
        raise HTTPException(status_code=400, detail="operation 不能为空")
    try:
        git_version_store.reject_forbidden_operation(operation)
    except ValueError as exc:
        return {"allowed": False, "operation": operation, "reason": str(exc)}
    return {"allowed": True, "operation": operation}


# 中文注释：写入共享记忆（run 目录 + 索引）
@app.post("/memory/shared/upsert")
def shared_memory_upsert(req: Dict[str, Any]):
    run_id = str(req.get("run_id") or "").strip()
    task_id = str(req.get("task_id") or "").strip()
    content = str(req.get("content") or "")
    if not run_id:
        raise HTTPException(status_code=400, detail="run_id 不能为空")
    if not task_id:
        raise HTTPException(status_code=400, detail="task_id 不能为空")
    if not content:
        raise HTTPException(status_code=400, detail="content 不能为空")

    payload = app.state.shared_memory_store.upsert_task_record(
        run_id=run_id,
        task_id=task_id,
        content=content,
        stage=str(req.get("stage") or "phase-1"),
        capability=str(req.get("capability") or "general"),
        agent=str(req.get("agent") or "orchestrator"),
        artifact_name=str(req.get("artifact_name") or "final.md"),
        metadata=req.get("metadata") if isinstance(req.get("metadata"), dict) else None,
    )
    return {"ok": True, "record": payload}


# 中文注释：检索共享记忆（按 run/task/stage/capability 过滤）
@app.post("/memory/shared/search")
def shared_memory_search(req: Dict[str, Any]):
    records = app.state.shared_memory_store.search_records(
        run_id=str(req.get("run_id") or "").strip() or None,
        task_id=str(req.get("task_id") or "").strip() or None,
        stage=str(req.get("stage") or "").strip() or None,
        capability=str(req.get("capability") or "").strip() or None,
        limit=int(req.get("limit") or 20),
    )
    return {"count": len(records), "records": records}
