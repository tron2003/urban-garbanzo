"""The agent: request -> workflow selection -> step execution -> result.

    User request
        -> WorkflowRouter   (LLM tool-calling, heuristic fallback)   which workflow? which parameters?
        -> params.resolve   (user > defaults > bundled samples)
        -> WorkflowEngine   (Excel step list, bound Python handlers) steps, tools, decisions, errors
        -> RunReport        (what was selected / executed / produced)

The agent also keeps a tiny conversation state (``Session``) so that when a workflow asks a question
("which order ID?") the user's next message completes that same run instead of being routed afresh.
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Any, Optional

from .config import Settings
from .core.engine import WorkflowEngine
from .core.errors import WorkflowConfigError
from .core.models import RunReport
from .core.registry import DEFAULT_REGISTRY, Registry, validate_bindings
from .excel_loader import WorkflowSpec, load_workflow_specs
from .llm import build_llm
from .params import resolve_params
from .router import RouteDecision, WorkflowRouter
from .tools.registry import ToolRegistry, ToolServices


@dataclass
class Session:
    pending_workflow: Optional[str] = None
    pending_params: dict[str, Any] = field(default_factory=dict)
    pending_missing: list[str] = field(default_factory=list)
    pending_choice: Optional[dict] = None       # {"request": str, "options": [workflow ids]}


@dataclass
class AgentResponse:
    request: str
    kind: str                      # completed | needs_input | failed | no_match | ambiguous
    route: Optional[RouteDecision] = None
    report: Optional[RunReport] = None
    message: str = ""
    options: list[tuple[str, str]] = field(default_factory=list)      # (workflow id, name) when ambiguous


class Agent:
    def __init__(self, settings: Optional[Settings] = None, llm=None, registry: Optional[Registry] = None,
                 strict: bool = True):
        self.settings = settings or Settings.from_env()
        self.llm = llm if llm is not None else build_llm(self.settings)
        self.registry = registry or DEFAULT_REGISTRY
        self.registry.discover()
        self.specs: list[WorkflowSpec] = load_workflow_specs(self.settings.workflow_excel)
        self.spec_by_id = {s.id: s for s in self.specs}
        self.tools = ToolRegistry(ToolServices(self.settings, self.llm))
        self.binding_errors, self.config_warnings = validate_bindings(self.specs, self.registry, self.tools)
        if self.binding_errors and strict:      # fail fast: Excel and code must agree
            raise WorkflowConfigError(self.binding_errors)
        self.engine = WorkflowEngine(self.registry, self.tools, self.settings, self.llm)
        self.router = WorkflowRouter(self.specs, self.registry, self.llm, self.settings)

    # ------------------------------------------------------------------ direct execution
    def run_workflow(self, workflow_id: str, provided: Optional[dict[str, Any]] = None) -> RunReport:
        spec = self.spec_by_id.get(workflow_id)
        if spec is None:
            raise WorkflowConfigError(f"Unknown workflow {workflow_id}")
        module = self.registry.get(workflow_id)
        params, sources = resolve_params(module, provided or {}, self.settings.allow_sample_defaults)
        return self.engine.execute(spec, params, sources)

    # ------------------------------------------------------------------ natural-language entry point
    def handle(self, request: str, session: Optional[Session] = None, overrides: Optional[dict[str, Any]] = None,
               workflow_id: Optional[str] = None) -> AgentResponse:
        session = session if session is not None else Session()
        text = (request or "").strip()
        overrides = overrides or {}

        if not text and not workflow_id:
            return AgentResponse(request, "no_match", message="Please type a request, e.g. 'Which products need restocking?'")

        # (a) the user is answering "which of these did you mean?"
        if session.pending_choice and text:
            picked = self._pick_option(text, session.pending_choice["options"])
            if picked:
                original = session.pending_choice["request"]
                session.pending_choice = None
                route = RouteDecision(picked, 1.0, "chosen by the user from the suggested options", "user-selected",
                                      params=self.router.extract_params(picked, original))
                return self._run(original, route, session, overrides)
            session.pending_choice = None

        # (b) the previous workflow asked a question: does this message answer it?
        if session.pending_workflow and text and not workflow_id:
            cont = self._continue_pending(text, session)
            if cont is not None:
                return self._run(text, cont, session, overrides)
            session.pending_workflow, session.pending_params, session.pending_missing = None, {}, []

        # (c) normal path: pick a workflow
        if workflow_id:
            if workflow_id not in self.spec_by_id:
                return AgentResponse(request, "no_match", message=f"Unknown workflow '{workflow_id}'. Known: {', '.join(self.spec_by_id)}")
            route = RouteDecision(workflow_id, 1.0, "selected explicitly (--workflow)", "explicit",
                                  params=self.router.extract_params(workflow_id, text))
        else:
            route = self.router.route(text)
        if route.workflow_id is None:
            return AgentResponse(request, "no_match", route=route, message=self._no_match_message(route))
        if route.ambiguous and route.method.startswith("heuristic"):
            opts = [(w, self.spec_by_id[w].name) for w, _ in route.candidates[:2]]
            session.pending_choice = {"request": text, "options": [o[0] for o in opts]}
            return AgentResponse(request, "ambiguous", route=route, options=opts,
                                 message="I could handle that in more than one way. Which did you mean?")
        return self._run(text, route, session, overrides)

    # ------------------------------------------------------------------ helpers
    def _run(self, text: str, route: RouteDecision, session: Session, overrides: dict[str, Any]) -> AgentResponse:
        module = self.registry.get(route.workflow_id)
        provided = dict(route.params)
        for k, v in overrides.items():                    # explicit --param wins over anything inferred
            p = module.param(k)
            if p is None:
                continue
            coerced = p.coerce(v)
            if coerced not in (None, [], ""):
                provided[k] = coerced
        report = self.run_workflow(route.workflow_id, provided)
        if report.status == "needs_input":
            session.pending_workflow, session.pending_params = route.workflow_id, provided
            session.pending_missing = report.clarification.missing if report.clarification else []
            return AgentResponse(text, "needs_input", route=route, report=report, message=report.clarification.message)
        session.pending_workflow, session.pending_params, session.pending_missing = None, {}, []
        if report.status == "failed":
            return AgentResponse(text, "failed", route=route, report=report, message=report.error)
        return AgentResponse(text, "completed", route=route, report=report)

    def _continue_pending(self, text: str, session: Session) -> Optional[RouteDecision]:
        wid = session.pending_workflow
        module = self.registry.get(wid)
        new = self.router.extract_params(wid, text)
        new = {k: v for k, v in new.items() if k not in session.pending_params or v != session.pending_params[k]}
        if not new and len(session.pending_missing) == 1:
            # a bare answer ("ORD-1002", "increase sales") - unless the user clearly asked for something else
            other = self.router.route_heuristic(text)
            if not (other.workflow_id and other.workflow_id != wid and not other.ambiguous):
                p = module.param(session.pending_missing[0])
                if p is not None and p.type != "file":
                    v = p.coerce(text)
                    if v not in (None, [], ""):
                        new = {p.name: v}
        if not new:
            return None
        return RouteDecision(wid, 1.0, "your reply answers the question I asked", "continued",
                             params={**session.pending_params, **new})

    def _pick_option(self, text: str, options: list[str]) -> Optional[str]:
        t = text.strip().lower()
        if t.isdigit() and 1 <= int(t) <= len(options):
            return options[int(t) - 1]
        for w in options:
            if t == w.lower() or t == self.spec_by_id[w].name.lower():
                return w
        return None

    def _no_match_message(self, route: RouteDecision) -> str:
        lines = ["I couldn't match that to one of my workflows. Here is what I can do:"]
        lines += [f"  {s.id}  {s.name} - {s.trigger}" for s in self.specs]
        return "\n".join(lines)
