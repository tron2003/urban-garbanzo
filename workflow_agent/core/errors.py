"""Exception types used to steer the workflow engine.

The engine treats each of these differently:

* NeedMoreInput  -> pause the workflow and ask the user (not a failure)
* StepError      -> the step cannot continue; run is marked failed, later steps skipped
* ToolError      -> a tool failed; TransientToolError is retried automatically
"""
from __future__ import annotations

from typing import Iterable, Optional


class WorkflowAgentError(Exception):
    """Base class for all errors raised by this package."""


class WorkflowConfigError(WorkflowAgentError):
    """The Excel workbook or the registered workflow code is inconsistent."""

    def __init__(self, problems: Iterable[str] | str):
        self.problems = [problems] if isinstance(problems, str) else list(problems)
        super().__init__("; ".join(self.problems))


class NeedMoreInput(WorkflowAgentError):
    """Raised by a step when a required input is missing or invalid.

    The agent turns this into a clarification question and remembers the
    partially-collected parameters so the user's next message can complete them.
    """

    def __init__(self, message: str, missing: Optional[list[str]] = None):
        super().__init__(message)
        self.message = message
        self.missing = missing or []


class StepError(WorkflowAgentError):
    """A step failed in a way the workflow cannot recover from."""

    def __init__(self, message: str, hint: Optional[str] = None):
        super().__init__(message)
        self.message = message
        self.hint = hint


class ToolError(WorkflowAgentError):
    def __init__(self, tool: str, message: str):
        super().__init__(f"{tool}: {message}")
        self.tool = tool
        self.message = message


class TransientToolError(ToolError):
    """Temporary failure (timeout, 5xx). The tool registry retries these."""


class ToolNotPermitted(ToolError):
    """A workflow tried to use a tool that its Excel row does not list."""


class LLMUnavailable(WorkflowAgentError):
    """No LLM is configured, or the call failed / returned unusable output."""

    def __init__(self, message: str, transient: bool = False):
        super().__init__(message)
        self.transient = transient
