"""Plain data containers shared across the engine, agent and renderers."""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Callable, Optional


@dataclass
class Param:
    """A workflow input. Used for (a) the LLM tool schema, (b) heuristic extraction,
    (c) defaults. Business validation still happens inside the workflow steps."""

    name: str
    description: str
    type: str = "string"                      # string | number | integer | boolean | array | file
    required: bool = False
    default: Any = None
    sample_default: Any = None                # bundled demo input (used only if allowed)
    sample_group: Optional[str] = None        # sample defaults in a group apply only if the user gave none of the group
    extractor: Optional[Callable[[str], Any]] = None   # heuristic: text -> value | None
    items: str = "string"                     # element type when type == "array"

    def json_schema(self) -> dict:
        t = "string" if self.type == "file" else self.type
        schema: dict[str, Any] = {"type": t, "description": self.description}
        if t == "array":
            schema["items"] = {"type": self.items}
        return schema

    def coerce(self, value: Any) -> Any:
        """Best-effort coercion of an LLM/user supplied value. Returns None if unusable."""
        if value is None or value == "":
            return None
        try:
            if self.type == "number":
                return float(str(value).replace(",", "").rstrip("%"))
            if self.type == "integer":
                return int(float(str(value).replace(",", "")))
            if self.type == "boolean":
                if isinstance(value, bool):
                    return value
                return str(value).strip().lower() in {"1", "true", "yes", "y"}
            if self.type == "array":
                if isinstance(value, (list, tuple)):
                    return [str(v).strip() for v in value if str(v).strip()]
                parts = [p.strip() for p in str(value).replace("\n", ",").replace(";", ",").split(",")]
                return [p for p in parts if p]
            return str(value).strip()
        except (TypeError, ValueError):
            return None


@dataclass
class Table:
    title: str
    columns: list[str]
    rows: list[list[Any]]
    note: str = ""


@dataclass
class WorkflowResult:
    summary: str = ""
    tables: list[Table] = field(default_factory=list)
    data: dict[str, Any] = field(default_factory=dict)
    artifacts: list[str] = field(default_factory=list)
    text_blocks: list[tuple[str, str]] = field(default_factory=list)   # (title, body)


@dataclass
class StepTrace:
    index: int
    name: str
    status: str = "pending"        # success | failed | skipped | needs_input | pending
    duration_ms: float = 0.0
    detail: str = ""
    error: str = ""
    error_type: str = ""


@dataclass
class ToolCallTrace:
    tool: str
    operation: str
    step: str
    duration_ms: float
    status: str                    # ok | error | retried
    attempts: int = 1
    error: str = ""


@dataclass
class Decision:
    step: str
    name: str
    outcome: str
    detail: str = ""


@dataclass
class Clarification:
    message: str
    missing: list[str] = field(default_factory=list)


@dataclass
class RunReport:
    run_id: str
    workflow_id: str
    workflow_name: str
    status: str                    # success | needs_input | failed
    params: dict[str, Any]
    param_sources: dict[str, str]
    steps: list[StepTrace]
    decisions: list[Decision]
    tool_calls: list[ToolCallTrace]
    warnings: list[str]
    result: Optional[WorkflowResult]
    clarification: Optional[Clarification]
    error: str = ""
    error_hint: str = ""
    duration_ms: float = 0.0
    decision_logic: str = ""
    expected_output: str = ""
