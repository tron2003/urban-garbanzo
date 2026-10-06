"""The agent: wires Excel specs, registry, tools, LLM and engine together."""
from __future__ import annotations

from typing import Any, Optional

from .config import Settings
from .core.engine import WorkflowEngine
from .core.errors import WorkflowConfigError
from .core.models import RunReport
from .core.registry import DEFAULT_REGISTRY, Registry, validate_bindings
from .excel_loader import WorkflowSpec, load_workflow_specs
from .llm import build_llm
from .params import resolve_params
from .tools.registry import ToolRegistry, ToolServices


class Agent:
    def __init__(self, settings: Optional[Settings] = None, llm=None, registry: Optional[Registry] = None):
        self.settings = settings or Settings.from_env()
        self.llm = llm if llm is not None else build_llm(self.settings)
        self.registry = registry or DEFAULT_REGISTRY
        self.registry.discover()
        self.specs: list[WorkflowSpec] = load_workflow_specs(self.settings.workflow_excel)
        self.spec_by_id = {s.id: s for s in self.specs}
        self.tools = ToolRegistry(ToolServices(self.settings, self.llm))
        errors, self.config_warnings = validate_bindings(self.specs, self.registry, self.tools)
        if errors:
            raise WorkflowConfigError(errors)
        self.engine = WorkflowEngine(self.registry, self.tools, self.settings, self.llm)

    # -- direct execution (no routing); used by tests, scripts and the router path --
    def run_workflow(self, workflow_id: str, provided: Optional[dict[str, Any]] = None) -> RunReport:
        spec = self.spec_by_id.get(workflow_id)
        if spec is None:
            raise WorkflowConfigError(f"Unknown workflow {workflow_id}")
        module = self.registry.get(workflow_id)
        params, sources = resolve_params(module, provided or {}, self.settings.allow_sample_defaults)
        return self.engine.execute(spec, params, sources)
