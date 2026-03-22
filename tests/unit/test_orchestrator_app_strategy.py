from __future__ import annotations

from types import SimpleNamespace

import shannon.orchestration.orchestrator.app as orchestrator_app


class _DummySessionManager:
	def __init__(self) -> None:
		self.messages = []

	def get_session(self, session_id: str):  # noqa: ANN001
		return None

	def create_session(self, session_id: str, user_id: str, tenant_id: str, metadata: dict):  # noqa: ANN001
		return SimpleNamespace(session_id=session_id, user_id=user_id, tenant_id=tenant_id, metadata=metadata)

	def add_message(self, session_id: str, role: str, content: str, metadata: dict):  # noqa: ANN001
		self.messages.append(
			{
				"session_id": session_id,
				"role": role,
				"content": content,
				"metadata": metadata,
			}
		)

	def update_context(self, session_id: str, key: str, value):  # noqa: ANN001
		return None


class _DummyStreamingManager:
	def __init__(self) -> None:
		self.events = []

	def publish(self, thread_id: str, event):  # noqa: ANN001
		self.events.append((thread_id, event))


class _DummyPgClient:
	def save_thread_state(self, thread_id: str, out: dict, status: str):  # noqa: ANN001
		return None


class _DummySharedStore:
	def ensure_run_manifest(self, run_id: str, manifest: dict):  # noqa: ANN001
		return None


class _DummyGraph:
	def invoke(self, state_in: dict, config: dict):  # noqa: ANN001
		return {
			"done": True,
			"errors": [],
			"final_output": {"summary": "ok"},
			"strategy": state_in.get("strategy"),
		}


class _ImmediateThread:
	def __init__(self, target, name=None, daemon=None):  # noqa: ANN001
		self._target = target

	def start(self):
		self._target()


def test_run_maps_legacy_strategy_and_emits_deprecation_observability(monkeypatch):
	monkeypatch.setattr(orchestrator_app.phase_gatekeeper, "can_enter", lambda run_id, phase: {"allowed": True, "gate_status": "open"})
	monkeypatch.setattr(orchestrator_app.threading, "Thread", _ImmediateThread)

	session_manager = _DummySessionManager()
	streaming_manager = _DummyStreamingManager()

	orchestrator_app.app.state.session_manager = session_manager
	orchestrator_app.app.state.streaming_manager = streaming_manager
	orchestrator_app.app.state.pg_client = _DummyPgClient()
	orchestrator_app.app.state.shared_memory_store = _DummySharedStore()
	orchestrator_app.app.state.graph = _DummyGraph()

	with orchestrator_app._run_registry_lock:
		orchestrator_app._run_registry.clear()

	resp = orchestrator_app.run({"thread_id": "thread-alias", "user_request": "hello", "strategy": "quick"})
	assert resp["status"] == "accepted"

	started_payload = None
	for _, event in streaming_manager.events:
		if getattr(event, "type", "") == "WORKFLOW_STARTED":
			started_payload = getattr(event, "payload", {})
			break

	assert started_payload is not None
	assert started_payload.get("strategy") == "deep"
	assert started_payload.get("strategy_requested") == "quick"
	assert started_payload.get("strategy_alias_deprecated") is True

	user_messages = [item for item in session_manager.messages if item.get("role") == "user"]
	assert user_messages
	metadata = user_messages[0]["metadata"]
	assert metadata["strategy"] == "deep"
	assert metadata["strategy_requested"] == "quick"
	assert metadata["strategy_alias_deprecated"] is True
