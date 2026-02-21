from __future__ import annotations

import json
from typing import Any, Dict, Optional

from shannon.storage.redis.session_manager import session_manager

# 中文注释：Thread Session 存储（兼容旧接口，底层复用 SessionManager）


class SessionStore:
    # 中文注释：函数 save 的入口
    def save(self, thread_id: str, payload: str) -> None:
        # 中文注释：若会话不存在则先创建，再把 payload 放入 context
        session = session_manager.get_session(thread_id)
        if session is None:
            session = session_manager.create_session(session_id=thread_id, user_id="anonymous")

        parsed_payload: Dict[str, Any]
        try:
            candidate = json.loads(payload)
            parsed_payload = candidate if isinstance(candidate, dict) else {"raw": payload}
        except Exception:
            parsed_payload = {"raw": payload}

        session.context["payload"] = parsed_payload
        session_manager.update_session(session)

    # 中文注释：函数 load 的入口
    def load(self, thread_id: str) -> str | None:
        session = session_manager.get_session(thread_id)
        if session is None:
            return None
        payload = session.context.get("payload") if isinstance(session.context, dict) else None
        if payload is None:
            return None
        return json.dumps(payload, ensure_ascii=False)

    # 中文注释：函数 load_session 的入口
    def load_session(self, thread_id: str) -> Optional[dict[str, Any]]:
        session = session_manager.get_session(thread_id)
        return session.to_dict() if session else None
