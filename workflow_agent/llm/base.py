"""LLM abstraction.

One tiny interface (``chat``) with two implementations:
  * OfflineLLM            - used when nothing is configured; callers fall back to heuristics/templates
  * OpenAICompatibleClient - OpenAI, Ollama, LM Studio, vLLM, Groq, OpenRouter... (chat/completions + tools)
"""
from __future__ import annotations

import json
import socket
import urllib.error
import urllib.request
from dataclasses import dataclass, field
from typing import Any, Optional

from ..core.errors import LLMUnavailable


@dataclass
class LLMToolCall:
    name: str
    arguments: dict[str, Any]


@dataclass
class LLMResponse:
    content: str = ""
    tool_calls: list[LLMToolCall] = field(default_factory=list)


class LLMClient:
    name = "none"
    available = False

    def chat(self, messages: list[dict], tools: Optional[list[dict]] = None,
             tool_choice: Any = None, json_mode: bool = False,
             temperature: float = 0.0, max_tokens: Optional[int] = None) -> LLMResponse:
        raise NotImplementedError


class OfflineLLM(LLMClient):
    name = "offline"
    available = False

    def chat(self, *args, **kwargs) -> LLMResponse:
        raise LLMUnavailable("No LLM configured (set LLM_PROVIDER / OPENAI_API_KEY in .env)")


class OpenAICompatibleClient(LLMClient):
    available = True

    def __init__(self, base_url: str, api_key: str, model: str, timeout: float = 60.0, label: str = "openai_compatible"):
        self.base_url = base_url.rstrip("/")
        self.api_key = api_key
        self.model = model
        self.timeout = timeout
        self.name = f"{label}:{model}"

    def chat(self, messages, tools=None, tool_choice=None, json_mode=False,
             temperature=0.0, max_tokens=None) -> LLMResponse:
        payload: dict[str, Any] = {"model": self.model, "messages": messages, "temperature": temperature}
        if tools:
            payload["tools"] = tools
            payload["tool_choice"] = tool_choice or "auto"
        if json_mode and not tools:
            payload["response_format"] = {"type": "json_object"}
        if max_tokens:
            payload["max_tokens"] = max_tokens
        headers = {"Content-Type": "application/json"}
        if self.api_key:
            headers["Authorization"] = f"Bearer {self.api_key}"
        req = urllib.request.Request(f"{self.base_url}/chat/completions",
                                     data=json.dumps(payload).encode("utf-8"), headers=headers, method="POST")
        try:
            with urllib.request.urlopen(req, timeout=self.timeout) as resp:
                body = json.loads(resp.read().decode("utf-8"))
        except urllib.error.HTTPError as exc:
            detail = ""
            try:
                detail = exc.read().decode("utf-8", "replace")[:200]
            except Exception:
                pass
            raise LLMUnavailable(f"LLM HTTP {exc.code}: {detail or exc.reason}",
                                 transient=exc.code in (408, 429, 500, 502, 503, 504)) from exc
        except (urllib.error.URLError, socket.timeout, TimeoutError, ConnectionError) as exc:
            raise LLMUnavailable(f"LLM endpoint unreachable: {getattr(exc, 'reason', exc)}", transient=True) from exc
        except json.JSONDecodeError as exc:
            raise LLMUnavailable("LLM returned a non-JSON response") from exc

        try:
            msg = body["choices"][0]["message"]
        except (KeyError, IndexError, TypeError) as exc:
            raise LLMUnavailable("LLM response had no choices/message") from exc
        calls: list[LLMToolCall] = []
        for tc in msg.get("tool_calls") or []:
            fn = tc.get("function", {})
            raw = fn.get("arguments", "{}")
            try:
                args = json.loads(raw) if isinstance(raw, str) else dict(raw)
            except (json.JSONDecodeError, TypeError):
                args = {}
            if fn.get("name"):
                calls.append(LLMToolCall(fn["name"], args if isinstance(args, dict) else {}))
        return LLMResponse(content=msg.get("content") or "", tool_calls=calls)


def build_llm(settings) -> LLMClient:
    provider = (settings.llm_provider or "none").lower()
    if provider in ("none", "off", "offline", ""):
        return OfflineLLM()
    if provider == "openai":
        if not settings.llm_api_key:
            return OfflineLLM()
        return OpenAICompatibleClient(settings.llm_base_url or "https://api.openai.com/v1",
                                      settings.llm_api_key, settings.llm_model or "gpt-4o-mini",
                                      settings.llm_timeout, "openai")
    if provider in ("openai_compatible", "ollama", "lmstudio"):
        base = settings.llm_base_url or ("http://localhost:11434/v1" if provider == "ollama" else "")
        if not base or not settings.llm_model:
            return OfflineLLM()
        return OpenAICompatibleClient(base, settings.llm_api_key, settings.llm_model, settings.llm_timeout, provider)
    return OfflineLLM()
