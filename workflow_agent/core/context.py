"""RunContext: the object every step handler receives."""
from __future__ import annotations

import csv
import time
from datetime import date
from pathlib import Path
from typing import Any, Iterable, Optional

from ..excel_loader import WorkflowSpec
from .errors import StepError, ToolError, ToolNotPermitted
from .models import Decision, Table, ToolCallTrace, WorkflowResult


class RunContext:
    def __init__(self, spec: WorkflowSpec, params: dict[str, Any], param_sources: dict[str, str],
                 settings, tools, llm, run_id: str):
        self.spec = spec
        self.params = params
        self.param_sources = param_sources
        self.settings = settings
        self.tools = tools
        self.llm = llm
        self.run_id = run_id
        self.state: dict[str, Any] = {}
        self.decisions: list[Decision] = []
        self.tool_calls: list[ToolCallTrace] = []
        self.warnings: list[str] = []
        self.result: Optional[WorkflowResult] = None
        self.current_step: str = ""
        self._allowed = {tools.resolve(t) for t in spec.tools} - {None}

    # ---- inputs -------------------------------------------------------
    def param(self, name: str, default: Any = None) -> Any:
        value = self.params.get(name)
        return default if value is None else value

    def source(self, name: str) -> str:
        return self.param_sources.get(name, "")

    @property
    def llm_available(self) -> bool:
        return bool(getattr(self.llm, "available", False))

    @property
    def today(self) -> date:
        return self.settings.current_date()

    def resolve_path(self, value: str | Path) -> Path:
        return self.settings.resolve(value)

    # ---- tools --------------------------------------------------------
    def call_tool(self, tool: str, **kwargs) -> Any:
        """Call a registered tool. Only tools listed in this workflow's Excel row are allowed."""
        if tool not in self._allowed:
            allowed = ", ".join(sorted(self._allowed)) or "none"
            err = ToolNotPermitted(tool, f"{self.spec.id} is not allowed to use this tool "
                                         f"(Excel Tools_Required resolves to: {allowed})")
            self.tool_calls.append(ToolCallTrace(tool, str(kwargs.get("op", "")), self.current_step, 0.0, "error", 0, err.message))
            raise err
        started = time.perf_counter()
        op = str(kwargs.get("op", ""))
        try:
            result, attempts = self.tools.call(tool, **kwargs)
        except ToolError as exc:
            ms = (time.perf_counter() - started) * 1000
            self.tool_calls.append(ToolCallTrace(tool, op, self.current_step, ms, "error",
                                                 self.settings.tool_max_retries + 1 if "Transient" in type(exc).__name__ else 1,
                                                 exc.message))
            raise
        ms = (time.perf_counter() - started) * 1000
        self.tool_calls.append(ToolCallTrace(tool, op, self.current_step, ms,
                                             "retried" if attempts > 1 else "ok", attempts))
        return result

    # ---- decisions, warnings, results ---------------------------------
    def decide(self, name: str, outcome: str, detail: str = "") -> None:
        self.decisions.append(Decision(self.current_step, name, outcome, detail))

    def warn(self, message: str) -> None:
        if message not in self.warnings:
            self.warnings.append(message)

    def set_result(self, summary: str, tables: Iterable[Table] = (), data: Optional[dict] = None,
                   artifacts: Iterable[str] = (), text_blocks: Iterable[tuple[str, str]] = ()) -> None:
        self.result = WorkflowResult(summary=summary, tables=list(tables), data=data or {},
                                     artifacts=list(artifacts), text_blocks=list(text_blocks))

    def write_artifact(self, filename: str, rows: list[dict], columns: list[str]) -> str:
        """Write a CSV next to this run's other outputs and return a project-relative path."""
        run_dir = self.settings.output_dir / self.run_id
        run_dir.mkdir(parents=True, exist_ok=True)
        path = run_dir / filename
        try:
            with path.open("w", newline="", encoding="utf-8") as fh:
                writer = csv.DictWriter(fh, fieldnames=columns, extrasaction="ignore")
                writer.writeheader()
                writer.writerows(rows)
        except OSError as exc:
            raise StepError(f"Could not write output file {filename}: {exc}",
                            hint="Check that the outputs/ folder is writable.") from exc
        try:
            return str(path.relative_to(self.settings.base_dir))
        except ValueError:
            return str(path)
