"""Binding between Excel workflow rows and executable Python.

A workflow module declares its executable steps like this::

    wf = WorkflowModule("WF011", params=[Param(...)])

    @wf.step("Load inventory")          # text must match the Excel step
    def load(ctx): ...

Importing the module registers it. ``Registry.discover()`` imports every module in
``workflow_agent.workflows`` automatically, so adding a workflow = one Excel row
plus one new .py file. No other file needs to change.
"""
from __future__ import annotations

import difflib
import importlib
import pkgutil
from typing import Callable, Iterable, Optional

from ..excel_loader import WorkflowSpec, norm_key
from .errors import WorkflowConfigError
from .models import Param

StepHandler = Callable[["RunContext"], Optional[str]]   # noqa: F821


class WorkflowModule:
    def __init__(self, workflow_id: str, params: Iterable[Param] = (),
                 routing_hints: Iterable[str] = (), registry: "Registry | None" = None):
        self.workflow_id = workflow_id
        self.params: list[Param] = list(params)
        self.routing_hints: list[str] = list(routing_hints)
        self.handlers: dict[str, StepHandler] = {}
        self.handler_names: dict[str, str] = {}
        (registry or DEFAULT_REGISTRY).register(self)

    def step(self, name: str, *aliases: str):
        def decorator(fn: StepHandler) -> StepHandler:
            for n in (name, *aliases):
                key = norm_key(n)
                if key in self.handlers:
                    raise WorkflowConfigError(f"{self.workflow_id}: duplicate handler for step '{n}'")
                self.handlers[key] = fn
                self.handler_names[key] = n
            return fn
        return decorator

    def param(self, name: str) -> Optional[Param]:
        return next((p for p in self.params if p.name == name), None)


class Registry:
    def __init__(self) -> None:
        self._modules: dict[str, WorkflowModule] = {}

    def register(self, module: WorkflowModule) -> None:
        if module.workflow_id in self._modules:
            raise WorkflowConfigError(f"Workflow {module.workflow_id} is registered twice")
        self._modules[module.workflow_id] = module

    def unregister(self, workflow_id: str) -> None:
        self._modules.pop(workflow_id, None)

    def get(self, workflow_id: str) -> Optional[WorkflowModule]:
        return self._modules.get(workflow_id)

    def ids(self) -> list[str]:
        return sorted(self._modules)

    def discover(self, package: str = "workflow_agent.workflows") -> None:
        """Import every module in the workflows package so its decorators run."""
        pkg = importlib.import_module(package)
        for info in pkgutil.iter_modules(pkg.__path__):
            if not info.name.startswith("_"):
                importlib.import_module(f"{package}.{info.name}")


DEFAULT_REGISTRY = Registry()


def validate_bindings(specs: list[WorkflowSpec], registry: Registry, tool_registry) -> tuple[list[str], list[str]]:
    """Check Excel <-> Python consistency. Returns (errors, warnings)."""
    errors: list[str] = []
    warnings: list[str] = []
    spec_ids = {s.id for s in specs}

    for spec in specs:
        module = registry.get(spec.id)
        if module is None:
            errors.append(f"{spec.id} ({spec.name}): in Excel but no Python module registers it. "
                          f"Create workflow_agent/workflows/<name>.py with WorkflowModule('{spec.id}').")
            continue

        excel_keys = {norm_key(s) for s in spec.steps}
        for step in spec.steps:
            if norm_key(step) not in module.handlers:
                close = difflib.get_close_matches(norm_key(step), list(module.handlers), n=1, cutoff=0.6)
                hint = f" (closest handler: '{module.handler_names[close[0]]}')" if close else ""
                errors.append(f"{spec.id}: Excel step '{step}' has no @step handler{hint}")
        for key, name in module.handler_names.items():
            if key not in excel_keys:
                errors.append(f"{spec.id}: handler '{name}' does not match any Excel step "
                              f"(was the step renamed in the workbook?)")

        for label in spec.tools:
            if tool_registry.resolve(label) is None:
                errors.append(f"{spec.id}: Excel tool '{label}' is not registered in workflow_agent/tools")

    for wid in registry.ids():
        if wid not in spec_ids:
            warnings.append(f"{wid}: Python module registered but no row in the Excel workbook (ignored)")
    return errors, warnings
