import os
from importlib import import_module

from shannon.storage.postgres.client import PostgresClient
from shannon.storage.qdrant.vector_store import VectorStore
from shannon.storage.redis.session_manager import SessionManager
from shannon.storage.redis.streaming_manager import Event, StreamingManager

session_module = import_module("shannon.storage.redis.session_manager")

# 中文注释：数据层稳定性测试（外部依赖不可用时应自动降级）


def test_postgres_client_fallback(monkeypatch):
    monkeypatch.delenv("POSTGRES_DSN", raising=False)
    client = PostgresClient()
    client.insert_checkpoint("t1", "cp-1")
    client.save_thread_state("t1", {"done": True}, status="completed")

    assert client.latest_checkpoint("t1") == "cp-1"
    state = client.get_thread_state("t1")
    assert state is not None
    assert state["status"] == "completed"


def test_session_manager_history_limit():
    manager = SessionManager(ttl_seconds=3600, max_history=2, cache_size=10)
    session = manager.create_session(session_id="s1", user_id="u1")

    manager.add_message(session.id, "user", "m1")
    manager.add_message(session.id, "assistant", "m2")
    manager.add_message(session.id, "user", "m3")

    loaded = manager.get_session("s1")
    assert loaded is not None
    assert len(loaded.history) == 2
    assert loaded.history[0].content == "m2"


def test_session_manager_sliding_ttl_refresh(monkeypatch):
    now = {"ts": 1000.0}
    monkeypatch.setattr(session_module.time, "time", lambda: now["ts"])

    manager = SessionManager(ttl_seconds=120, max_history=50, cache_size=10, max_rounds=5)
    session = manager.create_session(session_id="sliding-ttl", user_id="u1")
    assert int(session.expires_at) == 1120

    now["ts"] = 1060.0
    manager.add_message(session.id, "user", "q1")
    loaded = manager.get_session(session.id)
    assert loaded is not None
    assert int(loaded.expires_at) == 1180


def test_session_manager_round_window_only_keeps_latest_5_rounds():
    manager = SessionManager(ttl_seconds=3600, max_history=200, cache_size=10, max_rounds=5)
    session = manager.create_session(session_id="round-window", user_id="u1")

    for idx in range(1, 7):
        manager.add_message(session.id, "user", f"q{idx}")
        manager.add_message(session.id, "assistant", f"a{idx}")

    loaded = manager.get_session(session.id)
    assert loaded is not None
    user_messages = [msg.content for msg in loaded.history if msg.role == "user"]
    assistant_messages = [msg.content for msg in loaded.history if msg.role == "assistant"]
    assert user_messages == ["q2", "q3", "q4", "q5", "q6"]
    assert assistant_messages == ["a2", "a3", "a4", "a5", "a6"]


def test_streaming_manager_publish_and_replay():
    manager = StreamingManager(capacity=32)
    manager.publish("wf-1", Event(workflow_id="wf-1", type="WORKFLOW_STARTED", message="start"))
    manager.publish("wf-1", Event(workflow_id="wf-1", type="WORKFLOW_COMPLETED", message="done"))

    events = manager.replay_since("wf-1", since_seq=0, limit=10)
    assert len(events) >= 2
    assert events[-1].type == "WORKFLOW_COMPLETED"


def test_vector_store_fallback_search(monkeypatch):
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    store = VectorStore(default_collection="unit_test_memories")
    store.upsert_text("Shannon supports LangGraph orchestration", payload={"thread_id": "t-1"}, collection="unit_test_memories")

    hits = store.search_text("LangGraph orchestration", limit=3, collection="unit_test_memories")
    assert hits
    assert isinstance(hits[0].get("payload"), dict)
