"""Workflow selection + parameter extraction.

Two interchangeable strategies behind one interface:

1. LLM tool-calling (preferred when an LLM is configured): every workflow in the Excel file is exposed to the
   model as a callable "tool" generated from the spreadsheet row (name, trigger, inputs, expected output) and the
   workflow's declared parameters. The model picks one tool call; its arguments become the workflow parameters.
2. Heuristic router (offline / fallback): TF-IDF cosine similarity between the request and each workflow's
   description (name, trigger, inputs, outputs, Test_Questions examples, routing hints) + evidence from the
   workflows' own parameter extractors (e.g. an order id strongly implies WF005).

If the LLM is unreachable or returns something unusable the router transparently falls back to the heuristic and
says so in the decision.  Low-confidence / near-tie results are reported as ambiguous so the agent can ask.
"""
from __future__ import annotations

import json
import math
import re
from collections import Counter
from dataclasses import dataclass, field
from typing import Any, Optional

from .core.errors import LLMUnavailable
from .core.registry import Registry
from .excel_loader import WorkflowSpec

_STOP = set("""a an the and or of to for in on at by with from is are was were be been being this that these those it its
i me my we our you your please can could would should will shall do does did any all some each every about into over than
then there here what which who whom whose how when where why show give tell find get make need want let us them they their
as if so not no yes also just now today new more has have had""".split())
# words that carry intent even though they look like stop words
_KEEP = {"new", "find", "show"}
_SYN = {"restock": "reorder", "replenish": "reorder", "low": "low", "running": "run", "shipment": "ship", "shipped": "ship",
        "shipping": "ship", "dupe": "duplicate", "dupes": "duplicate", "failing": "fail", "failed": "fail", "failure": "fail",
        "failures": "fail", "errors": "error", "slowest": "slow", "keywords": "keyword", "campaigns": "campaign"}


def _stem(tok: str) -> str:
    tok = _SYN.get(tok, tok)
    for suf in ("ing", "ies", "es", "ed", "s"):
        if len(tok) > len(suf) + 3 and tok.endswith(suf):
            tok = tok[: -len(suf)] + ("y" if suf == "ies" else "")
            break
    return _SYN.get(tok, tok)


def tokenize(text: str) -> list[str]:
    toks = re.findall(r"[a-z0-9]+", (text or "").lower())
    return [_stem(t) for t in toks if (t not in _STOP or t in _KEEP) and len(t) > 1]


def tool_name(spec: WorkflowSpec) -> str:
    return f"{spec.id.lower()}_{re.sub(r'[^a-z0-9]+', '_', spec.name.lower()).strip('_')}"[:60]


@dataclass
class RouteDecision:
    workflow_id: Optional[str]
    confidence: float = 0.0
    reason: str = ""
    method: str = "heuristic"                 # llm-tool-call | heuristic | heuristic (LLM fallback) | continued | user-selected
    params: dict[str, Any] = field(default_factory=dict)
    candidates: list[tuple[str, float]] = field(default_factory=list)
    ambiguous: bool = False
    note: str = ""


class WorkflowRouter:
    def __init__(self, specs: list[WorkflowSpec], registry: Registry, llm, settings):
        self.specs = {s.id: s for s in specs}
        self.registry, self.llm, self.settings = registry, llm, settings
        self._build_index()

    # ------------------------------------------------------------------ heuristic index
    def _build_index(self) -> None:
        self.docs: dict[str, Counter] = {}
        for s in self.specs.values():
            module = self.registry.get(s.id)
            c: Counter = Counter()
            for text, w in ((s.name, 3), (s.trigger, 2), (s.inputs, 1), (s.expected_output, 1), (s.decision_logic, 1), (" ".join(s.steps), 1),
                            (" ".join(s.examples), 3), (" ".join(module.routing_hints if module else []), 3)):
                for t in tokenize(text):
                    c[t] += w
            self.docs[s.id] = c
        n = len(self.docs)
        df: Counter = Counter()
        for c in self.docs.values():
            df.update(c.keys())
        self.idf = {t: math.log((n + 1) / (d + 1)) + 1 for t, d in df.items()}
        self.vecs = {wid: {t: (1 + math.log(f)) * self.idf[t] for t, f in c.items()} for wid, c in self.docs.items()}
        self.norms = {wid: math.sqrt(sum(v * v for v in vec.values())) or 1.0 for wid, vec in self.vecs.items()}

    def _score_all(self, text: str) -> tuple[list[tuple[str, float]], dict[str, list[str]]]:
        q = Counter(tokenize(text))
        qvec = {t: (1 + math.log(f)) * self.idf.get(t, 0.0) for t, f in q.items() if t in self.idf}
        qnorm = math.sqrt(sum(v * v for v in qvec.values())) or 1.0
        scores, why = [], {}
        for wid, vec in self.vecs.items():
            dot, contrib = 0.0, []
            for t, qv in qvec.items():
                if t in vec:
                    dot += qv * vec[t]
                    contrib.append((qv * vec[t], t))
            cos = dot / (qnorm * self.norms[wid])
            # evidence from the workflow's own extractors (non-file params only: '.csv' appears everywhere)
            module = self.registry.get(wid)
            hits = []
            for p in (module.params if module else []):
                if p.extractor and p.type != "file":
                    try:
                        if p.coerce(p.extractor(text)) not in (None, [], ""):
                            hits.append(p.name)
                    except Exception:
                        pass
            bonus = min(0.12 * len(hits), 0.30)
            scores.append((wid, round(min(cos + bonus, 1.0), 3)))
            why[wid] = [t for _, t in sorted(contrib, reverse=True)[:4]] + [f"<{h} found>" for h in hits[:2]]
        scores.sort(key=lambda x: -x[1])
        return scores, why

    def route_heuristic(self, text: str, note: str = "", method: str = "heuristic") -> RouteDecision:
        scores, why = self._score_all(text)
        (top, s1), (second, s2) = scores[0], scores[1]
        if s1 < self.settings.router_min_score:
            return RouteDecision(None, s1, "no workflow is similar enough to the request", method, candidates=scores[:3], note=note)
        ambiguous = (s1 - s2) < self.settings.router_ambiguity_margin and s2 >= self.settings.router_min_score
        return RouteDecision(top, s1, "matched: " + (", ".join(why[top]) or "overall similarity"), method,
                             candidates=scores[:3], ambiguous=ambiguous, note=note)

    # ------------------------------------------------------------------ LLM tool-calling
    def _tools(self) -> list[dict]:
        tools = []
        for s in self.specs.values():
            module = self.registry.get(s.id)
            props = {p.name: p.json_schema() for p in (module.params if module else [])}
            ex = f" Example requests: {' | '.join(s.examples)}." if s.examples else ""
            tools.append({"type": "function", "function": {
                "name": tool_name(s),
                "description": f"{s.name}. Use when: {s.trigger}. Inputs: {s.inputs}. Produces: {s.expected_output}.{ex}",
                "parameters": {"type": "object", "properties": props, "additionalProperties": False}}})
        tools.append({"type": "function", "function": {
            "name": "no_matching_workflow",
            "description": "Call this when the request does not match any available workflow (small talk, unrelated questions).",
            "parameters": {"type": "object", "properties": {"reason": {"type": "string"}}, "required": ["reason"]}}})
        return tools

    SYSTEM = ("You are the workflow router of a business automation agent. Choose exactly ONE function that matches the "
              "user's request. Every workflow can run on bundled sample data and will itself ask the user for anything it "
              "still needs, so a missing file path, id, date or other input is NEVER a reason to refuse: pick the matching "
              "workflow and simply leave that argument out. Fill arguments ONLY with values the user actually stated; never "
              "guess file names, ids, dates or goals. Call no_matching_workflow ONLY when the request is unrelated to every "
              "workflow (small talk, general knowledge, other topics).")

    def route_llm(self, text: str) -> RouteDecision:
        resp = self.llm.chat([{"role": "system", "content": self.SYSTEM}, {"role": "user", "content": text}],
                             tools=self._tools(), tool_choice="required", temperature=0.0)
        by_tool = {tool_name(s): s for s in self.specs.values()}
        call = next((c for c in resp.tool_calls if c.name in by_tool or c.name == "no_matching_workflow"), None)
        if call is None:   # some local models answer in JSON text instead of calling the tool
            m = re.search(r"\{.*\}", resp.content or "", re.S)
            if m:
                try:
                    data = json.loads(m.group(0))
                    wid = str(data.get("workflow_id", "")).upper()
                    if wid in self.specs:
                        return RouteDecision(wid, 0.7, str(data.get("reason", "chosen by the model (JSON reply)")), "llm-json",
                                             params=self.ground_params(wid, data.get("arguments") or {}, text)[0])
                except json.JSONDecodeError:
                    pass
            raise LLMUnavailable("model did not call a workflow tool")
        if call.name == "no_matching_workflow":
            return RouteDecision(None, 0.0, str(call.arguments.get("reason", "model found no matching workflow")), "llm-tool-call")
        spec = by_tool[call.name]
        params, dropped = self.ground_params(spec.id, call.arguments, text)
        return RouteDecision(spec.id, 0.9, f"model selected '{spec.name}' via tool call", "llm-tool-call", params=params,
                             note=("ignored model arguments not found in your request: " + ", ".join(dropped)) if dropped else "")

    # ------------------------------------------------------------------ public API
    def route(self, text: str) -> RouteDecision:
        heuristic = self.route_heuristic(text)
        if getattr(self.llm, "available", False):
            try:
                d = self.route_llm(text)
                d.candidates = heuristic.candidates
                if d.workflow_id is None and heuristic.workflow_id and not heuristic.ambiguous \
                        and heuristic.confidence >= self.settings.router_override_score:
                    # Safety net: some models refuse when an optional input is missing. A strong, unambiguous
                    # deterministic match wins over a "no workflow" answer; out-of-scope requests score ~0 and stay unmatched.
                    heuristic.method = "heuristic (LLM said no match)"
                    heuristic.note = f"LLM answered: {d.reason[:160]}"
                    heuristic.params = self.fill_params(heuristic.workflow_id, text, {})
                    return heuristic
                if d.workflow_id:
                    d.params = self.fill_params(d.workflow_id, text, d.params)
                return d
            except LLMUnavailable as exc:
                heuristic.method = "heuristic (LLM fallback)"
                heuristic.note = f"LLM routing unavailable: {exc}"
        if heuristic.workflow_id:
            heuristic.params = self.fill_params(heuristic.workflow_id, text, {})
        return heuristic

    def coerce_params(self, workflow_id: str, raw: dict) -> dict[str, Any]:
        module = self.registry.get(workflow_id)
        out = {}
        for p in (module.params if module else []):
            if p.name in raw:
                v = p.coerce(raw[p.name])
                if v not in (None, [], ""):
                    out[p.name] = v
        return out

    def ground_params(self, workflow_id: str, raw: dict, text: str) -> tuple[dict[str, Any], list[str]]:
        """Coerce model-supplied arguments and keep only those grounded in the user's message.

        Small models sometimes invent plausible values (a file called 'inventory.csv', an order id that was never
        mentioned). A value is kept only if it appears in the request, contains digits that all appear in the request
        (so '1003' -> 'ORD-1003' is fine), or - for file parameters - names a file that really exists.
        Everything else is dropped and reported; the workflow then uses its default or asks the user."""
        module = self.registry.get(workflow_id)
        out: dict[str, Any] = {}
        dropped: list[str] = []
        for p in (module.params if module else []):
            if p.name not in raw:
                continue
            v = p.coerce(raw[p.name])
            if v in (None, [], ""):
                continue
            kept = self._keep_grounded(p, v, text)
            if kept in (None, [], ""):
                dropped.append(f"{p.name}={raw[p.name]!r}")
            else:
                out[p.name] = kept
        return out, dropped

    def _keep_grounded(self, p, value, text: str):
        if p.type == "boolean":
            return value
        t = " ".join((text or "").lower().split())
        t_nums = re.findall(r"\d+(?:\.\d+)?", t.replace(",", ""))

        def one(v) -> bool:
            if p.type in ("number", "integer"):
                f = float(v)
                return any(abs(float(n) - f) < 1e-9 for n in t_nums)
            s = " ".join(str(v).lower().split())
            if not s:
                return False
            if s in t:
                return True
            if p.type == "file":
                try:
                    return self.settings.resolve(str(v)).is_file()
                except OSError:
                    return False
            digits = re.findall(r"\d+", s)
            return bool(digits) and all(d in re.findall(r"\d+", t) for d in digits)

        if p.type == "array":
            kept = [i for i in value if one(i)]
            return kept
        return value if one(value) else None

    def fill_params(self, workflow_id: str, text: str, have: dict[str, Any]) -> dict[str, Any]:
        """Add values found by the workflows' own extractors for anything the LLM did not supply."""
        module = self.registry.get(workflow_id)
        out = dict(have)
        for p in (module.params if module else []):
            if p.name in out or not p.extractor:
                continue
            try:
                v = p.coerce(p.extractor(text))
            except Exception:
                v = None
            if v not in (None, [], ""):
                out[p.name] = v
        return out

    def extract_params(self, workflow_id: str, text: str) -> dict[str, Any]:
        return self.fill_params(workflow_id, text, {})
