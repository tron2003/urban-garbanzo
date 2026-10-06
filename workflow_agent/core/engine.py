"""The generic workflow executor. It knows nothing about any specific workflow.

Given a WorkflowSpec (from Excel) and its WorkflowModule (Python bindings) it:
  1. walks the Excel step list in order,
  2. runs the bound handler for each step with timing,
  3. turns NeedMoreInput / StepError / unexpected exceptions into clean statuses,
  4. marks the remaining steps 'skipped' after a stop,
  5. returns a RunReport (steps, decisions, tool calls, warnings, result).
"""
from __future__ import annotations

import time
import traceback
import uuid
from datetime import datetime
from typing import Any, Optional

from ..excel_loader import WorkflowSpec, norm_key
from .context import RunContext
from .errors import NeedMoreInput, StepError, ToolError
from .models import Clarification, RunReport, StepTrace
from .registry import Registry
from .run_logger import RunLogger


class WorkflowEngine:
    def __init__(self, registry: Registry, tools, settings, llm, logger: Optional[RunLogger] = None):
        self.registry = registry
        self.tools = tools
        self.settings = settings
        self.llm = llm
        self.logger = logger or RunLogger(settings.log_file)

    def execute(self, spec: WorkflowSpec, params: dict[str, Any],
                param_sources: Optional[dict[str, str]] = None) -> RunReport:
        module = self.registry.get(spec.id)
        run_id = datetime.now().strftime("%Y%m%d-%H%M%S-") + uuid.uuid4().hex[:6]
        ctx = RunContext(spec, params, param_sources or {}, self.settings, self.tools, self.llm, run_id)
        traces = [StepTrace(index=i + 1, name=s) for i, s in enumerate(spec.steps)]
        status, error, hint = "success", "", ""
        clarification: Optional[Clarification] = None
        run_started = time.perf_counter()

        for trace in traces:
            handler = module.handlers.get(norm_key(trace.name)) if module else None
            if handler is None:      # normally caught at startup by validate_bindings
                trace.status, trace.error = "failed", "No handler is bound to this step"
                trace.error_type = "ConfigError"
                status, error = "failed", f"Step '{trace.name}' has no handler"
                break
            ctx.current_step = trace.name
            started = time.perf_counter()
            try:
                detail = handler(ctx)
                trace.status = "success"
                trace.detail = detail or ""
            except NeedMoreInput as exc:
                trace.status, trace.error_type, trace.error = "needs_input", "NeedMoreInput", exc.message
                status, clarification = "needs_input", Clarification(exc.message, exc.missing)
            except StepError as exc:
                trace.status, trace.error_type, trace.error = "failed", "StepError", exc.message
                status, error, hint = "failed", exc.message, exc.hint or ""
            except ToolError as exc:
                trace.status, trace.error_type, trace.error = "failed", type(exc).__name__, exc.message
                status, error = "failed", f"Tool '{exc.tool}' failed: {exc.message}"
            except Exception as exc:   # a bug or unexpected data: never crash the agent
                trace.status, trace.error_type = "failed", type(exc).__name__
                trace.error = f"{type(exc).__name__}: {exc}"
                status, error = "failed", f"Unexpected error in step '{trace.name}': {exc}"
                ctx.warn("Internal traceback: " + traceback.format_exc(limit=3).strip().splitlines()[-1])
            finally:
                trace.duration_ms = (time.perf_counter() - started) * 1000
            if status != "success":
                break

        # everything after the stopping point is skipped
        for t in traces:
            if t.status == "pending":
                t.status = "skipped"

        if status == "success" and ctx.result is None:
            status, error = "failed", "Workflow finished all steps but produced no result"

        report = RunReport(
            run_id=run_id, workflow_id=spec.id, workflow_name=spec.name, status=status,
            params=params, param_sources=param_sources or {}, steps=traces,
            decisions=ctx.decisions, tool_calls=ctx.tool_calls, warnings=ctx.warnings,
            result=ctx.result if status == "success" else None, clarification=clarification,
            error=error, error_hint=hint, duration_ms=(time.perf_counter() - run_started) * 1000,
            decision_logic=spec.decision_logic, expected_output=spec.expected_output,
        )
        self.logger.log(report)
        return report
