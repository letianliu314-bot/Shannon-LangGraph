from __future__ import annotations

import os
from typing import Any, Dict, Optional

from dotenv import find_dotenv, load_dotenv

# 中文注释：OpenAI API 调用封装（支持真实调用 + 无 Key 时的 stub）


class OpenAIClient:
    # 中文注释：函数 __init__ 的入口
    def __init__(self) -> None:
        # 中文注释：优先读取进程环境变量中的 OpenAI Key
        self.api_key = os.getenv("OPENAI_API_KEY")
        # 中文注释：若未注入环境变量，回退尝试自动加载项目 .env
        if not self.api_key:
            try:
                dotenv_path = find_dotenv(usecwd=True)
                if dotenv_path:
                    load_dotenv(dotenv_path=dotenv_path, override=False)
                    self.api_key = os.getenv("OPENAI_API_KEY")
            except Exception:
                # 中文注释：dotenv 加载失败不阻断，继续走 stub/fallback
                pass
        # 中文注释：延迟初始化 SDK 客户端，避免无依赖环境直接报错
        self._sdk_client: Optional[object] = None
        # 中文注释：统一 API 超时，避免单次调用无限挂起拖垮上游编排
        timeout_raw = os.getenv("OPENAI_TIMEOUT_SECONDS", "45").strip()
        try:
            self.timeout_seconds = float(timeout_raw)
        except Exception:  # noqa: BLE001
            self.timeout_seconds = 45.0

    # 中文注释：函数 _get_sdk_client 的入口
    def _get_sdk_client(self):
        # 中文注释：无 Key 时直接返回空
        if not self.api_key:
            return None
        if self._sdk_client is not None:
            return self._sdk_client

        try:
            from openai import OpenAI  # type: ignore

            self._sdk_client = OpenAI(api_key=self.api_key, timeout=self.timeout_seconds)
        except Exception:  # noqa: BLE001
            # 中文注释：SDK 不可用时回退 stub 行为
            self._sdk_client = None
        return self._sdk_client

    # 中文注释：函数 _omit_temperature_for_model 的入口
    def _omit_temperature_for_model(self, model: str) -> bool:
        lowered = str(model or "").strip().lower()
        # 中文注释：gpt-5-nano 不支持自定义 temperature，需省略该参数
        return lowered.startswith("gpt-5-nano")

    # 中文注释：函数 _is_temperature_unsupported_error 的入口
    def _is_temperature_unsupported_error(self, exc: Exception) -> bool:
        message = str(exc).lower()
        return (
            "temperature" in message
            and (
                "unsupported value" in message
                or "does not support" in message
                or "only the default" in message
            )
        )

    # 中文注释：函数 _chat_complete 的入口
    def _chat_complete(self, client: Any, model: str, messages: list[dict[str, str]], temperature: float, omit_temperature: bool):
        payload: Dict[str, Any] = {
            "model": model,
            "messages": messages,
        }
        if not omit_temperature:
            payload["temperature"] = temperature
        return client.chat.completions.create(**payload)  # type: ignore[attr-defined]

    # 中文注释：函数 complete 的入口
    def complete(
        self,
        prompt: str,
        model: str,
        temperature: float,
        system_prompt: str | None = None,
        max_tokens: int | None = None,
        request_timeout: float | None = None,
    ) -> str:
        # 中文注释：未配置 Key 时返回可观测的占位内容
        if not self.api_key:
            role_hint = f"sys:{system_prompt[:24]} | " if system_prompt else ""
            return f"[stub:{model}] {role_hint}{prompt[:160]}"

        client = self._get_sdk_client()
        if client is None:
            role_hint = f"sys:{system_prompt[:24]} | " if system_prompt else ""
            return f"[fallback:{model}] {role_hint}{prompt[:160]}"

        messages = []
        if system_prompt:
            messages.append({"role": "system", "content": system_prompt})
        messages.append({"role": "user", "content": prompt})

        request_max_tokens = None
        if max_tokens is not None:
            try:
                request_max_tokens = max(64, int(max_tokens))
            except Exception:  # noqa: BLE001
                request_max_tokens = None

        request_timeout_value = None
        if request_timeout is not None:
            try:
                request_timeout_value = max(1.0, float(request_timeout))
            except Exception:  # noqa: BLE001
                request_timeout_value = None

        omit_temperature = self._omit_temperature_for_model(model)
        try:
            # 中文注释：优先使用 chat.completions 接口，兼容性更好
            payload: Dict[str, Any] = {
                "model": model,
                "messages": messages,
            }
            if not omit_temperature:
                payload["temperature"] = temperature
            if request_max_tokens is not None:
                payload["max_tokens"] = request_max_tokens
            if request_timeout_value is not None:
                payload["timeout"] = request_timeout_value
            response = client.chat.completions.create(**payload)  # type: ignore[attr-defined]
            content = response.choices[0].message.content
            return content or ""
        except Exception as exc:  # noqa: BLE001
            # 中文注释：若模型不支持温度参数，自动重试一次（不带 temperature）
            if (not omit_temperature) and self._is_temperature_unsupported_error(exc):
                try:
                    retry_payload: Dict[str, Any] = {
                        "model": model,
                        "messages": messages,
                    }
                    if request_max_tokens is not None:
                        retry_payload["max_tokens"] = request_max_tokens
                    if request_timeout_value is not None:
                        retry_payload["timeout"] = request_timeout_value
                    response = client.chat.completions.create(**retry_payload)  # type: ignore[attr-defined]
                    content = response.choices[0].message.content
                    return content or ""
                except Exception as retry_exc:  # noqa: BLE001
                    return f"[error:{model}] {type(retry_exc).__name__}: {str(retry_exc)[:120]}"
            # 中文注释：线上调用失败时返回降级文本，避免流程中断
            return f"[error:{model}] {type(exc).__name__}: {str(exc)[:120]}"
