from __future__ import annotations

import os
from typing import Any, Dict

import httpx

# 中文注释：Orchestrator 到 LLM Service 的 HTTP 客户端


class LLMServiceClient:
    # 中文注释：函数 __init__ 的入口
    def __init__(self, base_url: str, timeout: float = 120.0, max_retries: int = 2) -> None:
        timeout_raw = os.getenv("ORCH_LLM_SERVICE_TIMEOUT_SECONDS", "").strip()
        if timeout_raw:
            try:
                timeout = float(timeout_raw)
            except Exception:  # noqa: BLE001
                pass
        retries_raw = os.getenv("ORCH_LLM_SERVICE_RETRIES", "").strip()
        if retries_raw:
            try:
                max_retries = int(retries_raw)
            except Exception:  # noqa: BLE001
                pass
        self.base_url = base_url.rstrip("/")
        self.timeout = timeout
        self.max_retries = max(0, max_retries)

    def _resolve_timeout(self, path: str, timeout: float | None) -> float:
        if timeout is not None:
            return max(1.0, float(timeout))
        env_key_map = {
            "/agent/refine": "ORCH_LLM_SERVICE_TIMEOUT_REFINE_SECONDS",
            "/agent/decompose": "ORCH_LLM_SERVICE_TIMEOUT_DECOMPOSE_SECONDS",
            "/agent/run": "ORCH_LLM_SERVICE_TIMEOUT_RUN_SECONDS",
            "/v1/responses": "ORCH_LLM_SERVICE_TIMEOUT_RESPONSES_SECONDS",
        }
        env_key = env_key_map.get(path)
        if env_key:
            env_value = os.getenv(env_key, "").strip()
            if env_value:
                try:
                    return max(1.0, float(env_value))
                except Exception:  # noqa: BLE001
                    pass
        path_default_timeout = {
            # 中文注释：finalize 依赖 /v1/responses 汇总大文本，默认给更高超时窗口避免误超时
            "/v1/responses": 300.0,
        }.get(path)
        if path_default_timeout is not None:
            return max(1.0, float(max(self.timeout, path_default_timeout)))
        return max(1.0, float(self.timeout))

    def _resolve_retries(self, path: str, max_retries: int | None) -> int:
        if max_retries is not None:
            return max(0, int(max_retries))
        env_key_map = {
            "/agent/refine": "ORCH_LLM_SERVICE_RETRIES_REFINE",
            "/agent/decompose": "ORCH_LLM_SERVICE_RETRIES_DECOMPOSE",
            "/agent/run": "ORCH_LLM_SERVICE_RETRIES_RUN",
            "/v1/responses": "ORCH_LLM_SERVICE_RETRIES_RESPONSES",
        }
        env_key = env_key_map.get(path)
        if env_key:
            env_value = os.getenv(env_key, "").strip()
            if env_value:
                try:
                    return max(0, int(env_value))
                except Exception:  # noqa: BLE001
                    pass
        return max(0, int(self.max_retries))

    # 中文注释：函数 _post_json 的入口
    def _post_json(
        self,
        path: str,
        payload: Dict[str, Any],
        timeout: float | None = None,
        max_retries: int | None = None,
    ) -> Dict[str, Any]:
        last_error: Exception | None = None
        url = f"{self.base_url}{path}"
        request_timeout = self._resolve_timeout(path, timeout)
        retries = self._resolve_retries(path, max_retries)

        for _ in range(retries + 1):
            try:
                with httpx.Client(timeout=request_timeout) as client:
                    response = client.post(url, json=payload)
                    response.raise_for_status()
                    data = response.json()
                    if isinstance(data, dict):
                        return data
                    return {"data": data}
            except Exception as exc:  # noqa: BLE001
                last_error = exc

        error_message = str(last_error) if last_error else "unknown http error"
        raise RuntimeError(f"LLM Service request failed: {path}, error={error_message}")

    # 中文注释：函数 refine 的入口
    def refine(
        self,
        user_request: str,
        strategy: str,
        timeout: float | None = None,
        max_retries: int | None = None,
    ) -> Dict[str, Any]:
        return self._post_json(
            "/agent/refine",
            {
                "user_request": user_request,
                "strategy": strategy,
            },
            timeout=timeout,
            max_retries=max_retries,
        )

    # 中文注释：函数 decompose 的入口
    def decompose(
        self,
        user_request: str,
        strategy: str,
        refined: Dict[str, Any],
        max_tasks: int,
        role_preset: str,
        model_tier_hint: str | None = None,
        timeout: float | None = None,
        max_retries: int | None = None,
    ) -> Dict[str, Any]:
        return self._post_json(
            "/agent/decompose",
            {
                "user_request": user_request,
                "strategy": strategy,
                "refined": refined,
                "max_tasks": max_tasks,
                "role_preset": role_preset,
                "model_tier_hint": model_tier_hint or "",
            },
            timeout=timeout,
            max_retries=max_retries,
        )

    # 中文注释：函数 run_task 的入口
    def run_task(
        self,
        user_request: str,
        strategy: str,
        refined: Dict[str, Any],
        task: Dict[str, Any],
        previous_results: Dict[str, Any] | None = None,
        timeout: float | None = None,
        max_retries: int | None = None,
        strict_output: bool = False,
        quality_mode: str = "best_effort",
    ) -> Dict[str, Any]:
        return self._post_json(
            "/agent/run",
            {
                "user_request": user_request,
                "strategy": strategy,
                "refined": refined,
                "task": task,
                "previous_results": previous_results or {},
                "strict_output": strict_output,
                "quality_mode": quality_mode,
            },
            timeout=timeout,
            max_retries=max_retries,
        )

    # 中文注释：函数 respond 的入口
    def respond(
        self,
        prompt: str,
        model_tier: str,
        system_prompt: str | None = None,
        timeout: float | None = None,
        max_retries: int | None = None,
    ) -> Dict[str, Any]:
        payload: Dict[str, Any] = {
            "prompt": prompt,
            "model_tier": model_tier,
            "temperature": 0.2,
        }
        if system_prompt:
            payload["system_prompt"] = system_prompt
        return self._post_json("/v1/responses", payload, timeout=timeout, max_retries=max_retries)
