"""Tool registry: the only way workflow steps touch data, files, APIs or the LLM.

Every call goes through ``ToolRegistry.call`` which gives us, in one place:
  * permission checks (a workflow may only use tools listed in its Excel row)
  * automatic retry with back-off for TransientToolError
  * uniform error wrapping
  * timing for the execution trace
"""
from __future__ import annotations

import re
import time
from dataclasses import dataclass, field
from typing import Any, Callable, Optional

from ..core.errors import ToolError, TransientToolError


@dataclass
class ToolDef:
    name: str
    fn: Callable[..., Any]
    aliases: tuple[str, ...]
    description: str


_TOOL_DEFS: list[ToolDef] = []


def tool(name: str, aliases: tuple[str, ...] = (), description: str = ""):
    """Register a function as a tool. Signature: fn(services, **kwargs)."""
    def decorator(fn):
        _TOOL_DEFS.append(ToolDef(name=name, fn=fn, aliases=tuple(aliases), description=description or (fn.__doc__ or "").strip()))
        return fn
    return decorator


def _key(label: str) -> str:
    return re.sub(r"[^a-z0-9]+", "", str(label).lower())


@dataclass
class ToolServices:
    """Everything a tool may need besides its own arguments."""
    settings: Any
    llm: Any
    shared: dict = field(default_factory=dict)     # per-agent mutable state (e.g. simulated API counters)


class ToolRegistry:
    def __init__(self, services: ToolServices):
        import importlib, pkgutil
        import workflow_agent.tools as pkg
        for info in pkgutil.iter_modules(pkg.__path__):       # import every tool module -> decorators run
            if info.name != "registry" and not info.name.startswith("_"):
                importlib.import_module(f"workflow_agent.tools.{info.name}")
        self.services = services
        self._tools: dict[str, ToolDef] = {}
        self._labels: dict[str, str] = {}
        for d in _TOOL_DEFS:
            self._tools[d.name] = d
            for label in (d.name, *d.aliases):
                self._labels[_key(label)] = d.name

    def names(self) -> list[str]:
        return sorted(self._tools)

    def resolve(self, label: str) -> Optional[str]:
        """Map an Excel 'Tools_Required' label (e.g. 'CSV reader') to a registered tool name."""
        return self._labels.get(_key(label))

    def call(self, name: str, **kwargs) -> tuple[Any, int]:
        """Execute a tool; returns (result, attempts). Raises ToolError."""
        d = self._tools.get(name)
        if d is None:
            raise ToolError(name, "unknown tool")
        retries = max(0, int(self.services.settings.tool_max_retries))
        backoff = float(self.services.settings.tool_retry_backoff_s)
        attempt = 0
        while True:
            attempt += 1
            try:
                return d.fn(self.services, **kwargs), attempt
            except TransientToolError:
                if attempt > retries:
                    raise
                time.sleep(backoff * attempt)
            except ToolError:
                raise
            except (FileNotFoundError, PermissionError, IsADirectoryError) as exc:
                raise ToolError(name, f"file problem: {exc}") from exc
            except Exception as exc:                      # tool bug / unexpected data -> uniform error
                raise ToolError(name, f"{type(exc).__name__}: {exc}") from exc
