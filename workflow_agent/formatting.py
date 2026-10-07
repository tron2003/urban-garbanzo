"""Turn an AgentResponse into text, markdown or JSON. No business logic lives here."""
from __future__ import annotations

import json
from collections import OrderedDict
from datetime import date, datetime
from decimal import Decimal
from pathlib import Path
from typing import Any

from .agent import AgentResponse
from .core.models import Table

ICON = {"success": "OK  ", "failed": "FAIL", "skipped": "skip", "needs_input": "ASK ", "pending": "... "}


def _cell(v: Any) -> str:
    if isinstance(v, Decimal):
        v = float(v)
    if isinstance(v, float):
        v = f"{v:,.2f}".rstrip("0").rstrip(".") if v != int(v) else f"{int(v):,}"
    return " ".join(str(v if v is not None else "").split())


def _clip(s: str, n: int) -> str:
    return s if len(s) <= n else s[: n - 1] + "…"


def _text_table(t: Table, max_rows: int, max_col: int = 46) -> list[str]:
    rows = [[_cell(c) for c in r] for r in t.rows[:max_rows]]
    heads = [str(c) for c in t.columns]
    widths = [min(max([len(h)] + [len(r[i]) for r in rows if i < len(r)]), max_col) for i, h in enumerate(heads)]
    line = lambda cells: "  " + " | ".join(_clip(c, w).ljust(w) for c, w in zip(cells, widths)).rstrip()
    out = [f"  {t.title}", line(heads), "  " + "-+-".join("-" * w for w in widths)]
    out += [line(r) for r in rows]
    if len(t.rows) > max_rows:
        out.append(f"  ... {len(t.rows) - max_rows} more row(s) (full data in the saved file / --json)")
    if t.note:
        out.append(f"  ({t.note})")
    return out


def _tool_summary(report) -> list[str]:
    groups: "OrderedDict[tuple, list]" = OrderedDict()
    for c in report.tool_calls:
        groups.setdefault((c.tool, c.operation, c.status), []).append(c)
    lines = []
    for (tool, op, status), calls in groups.items():
        name = f"{tool}.{op}" if op else tool
        ms = sum(c.duration_ms for c in calls)
        extra = ""
        if status == "retried":
            extra = f" - succeeded after retry ({calls[0].attempts} attempts)"
        elif status == "error":
            extra = f" - FAILED: {calls[0].error}"
        lines.append(f"  {name} x{len(calls)} ({ms:.0f} ms){extra}")
    return lines


def render_text(resp: AgentResponse, max_rows: int = 15) -> str:
    out: list[str] = []
    bar = "=" * 78
    out += [bar, f" Request: {resp.request}", bar]
    r = resp.route
    if resp.kind in ("no_match", "ambiguous") or resp.report is None:
        if r and r.workflow_id is None:
            out.append(f" Selected workflow : none ({r.reason})")
            if r.note:
                out.append(f" Routing note      : {r.note}")
        out.append("")
        out.append(resp.message)
        for i, (wid, name) in enumerate(resp.options, 1):
            out.append(f"  {i}. {wid} - {name}")
        if resp.kind == "ambiguous":
            out.append("Reply with 1 or 2 (or the workflow ID).")
        return "\n".join(out)

    rep = resp.report
    out.append(f" Selected workflow : {rep.workflow_id} - {rep.workflow_name}")
    if r:
        conf = f", confidence {r.confidence:.2f}" if r.method.startswith("heuristic") else ""
        out.append(f" Routing           : {r.method}{conf}")
        out.append(f" Why               : {r.reason}")
        if r.note:
            out.append(f" Routing note      : {r.note}")
        if r.candidates and r.method.startswith("heuristic") and len(r.candidates) > 1:
            out.append(f" Runner-up         : {r.candidates[1][0]} ({r.candidates[1][1]:.2f})")
    shown = []
    for k, v in rep.params.items():
        src = rep.param_sources.get(k, "")
        val = ", ".join(map(str, v)) if isinstance(v, list) else str(v)
        shown.append(f"{k}={_clip(val, 60)}" + (" [bundled sample]" if src == "sample" else " [default]" if src == "default" else ""))
    out.append(f" Parameters        : {'; '.join(shown) if shown else '(none)'}")
    out.append("")
    out.append("Steps executed")
    for s in rep.steps:
        out.append(f"  {s.index}. [{ICON.get(s.status, s.status)}] {s.name}" + (f"  ({s.duration_ms:.0f} ms)" if s.status not in ('skipped', 'pending') else ""))
        if s.detail:
            out.append(f"        {s.detail}")
        if s.error:
            out.append(f"        ! {s.error}")
    out.append("")
    out.append("Conditions / decisions" + (f"   [Excel rule: {rep.decision_logic}]" if rep.decision_logic else ""))
    out += [f"  - {d.name}: {d.outcome}" + (f"  ({d.detail})" if d.detail else "") for d in rep.decisions] or ["  (none triggered)"]
    out.append("")
    out.append("Tools / API calls")
    out += _tool_summary(rep) or ["  (none)"]
    if rep.warnings:
        out += ["", "Warnings"] + [f"  ! {w}" for w in rep.warnings]
    out += ["", f"Result  [{rep.status.upper().replace('_', ' ')}, {rep.duration_ms:.0f} ms total]"]
    if rep.status == "success" and rep.result:
        out.append(f"  {rep.result.summary}")
        for t in rep.result.tables:
            out.append("")
            out += _text_table(t, max_rows)
        for title, body in rep.result.text_blocks:
            out += ["", f"  {title}"] + [f"    {line}" for line in body.splitlines()]
        if rep.result.artifacts:
            out += ["", "Files written"] + [f"  {a}" for a in rep.result.artifacts]
    elif rep.status == "needs_input":
        out.append(f"  I need more information: {rep.clarification.message}")
    else:
        out.append(f"  The workflow could not complete: {rep.error}")
        if rep.error_hint:
            out.append(f"  Hint: {rep.error_hint}")
    return "\n".join(out)


def render_markdown(resp: AgentResponse, max_rows: int = 40) -> str:
    rep, r = resp.report, resp.route
    md = [f"### Request\n\n> {resp.request}\n"]
    if rep is None:
        return "\n".join(md + [resp.message])
    md.append(f"**Selected workflow:** `{rep.workflow_id}` - {rep.workflow_name}  ")
    if r:
        md.append(f"**Routing:** {r.method}" + (f" (confidence {r.confidence:.2f})" if r.method.startswith("heuristic") else "") + f" - {r.reason}  ")
    shown = [f"`{k}={v}`" + (" *(bundled sample)*" if rep.param_sources.get(k) == "sample" else "") for k, v in rep.params.items()]
    md.append(f"**Parameters:** {', '.join(shown) or '(none)'}\n")
    md.append("**Steps executed**\n")
    for s in rep.steps:
        md.append(f"{s.index}. **{s.status}** - {s.name}" + (f" - {s.detail}" if s.detail else "") + (f" - _{s.error}_" if s.error else ""))
    md.append("\n**Conditions / decisions**\n")
    md += [f"- {d.name}: **{d.outcome}**" + (f" ({d.detail})" if d.detail else "") for d in rep.decisions] or ["- none triggered"]
    md.append("\n**Tools / API calls**\n")
    md += [f"- {line.strip()}" for line in _tool_summary(rep)] or ["- none"]
    if rep.warnings:
        md += ["\n**Warnings**\n"] + [f"- {w}" for w in rep.warnings]
    md.append(f"\n**Result ({rep.status})**\n")
    if rep.status == "success":
        md.append(rep.result.summary + "\n")
        for t in rep.result.tables:
            md.append(f"_{t.title}_\n")
            md.append("| " + " | ".join(map(str, t.columns)) + " |")
            md.append("|" + "|".join("---" for _ in t.columns) + "|")
            md += ["| " + " | ".join(_cell(c).replace("|", "/") for c in row) + " |" for row in t.rows[:max_rows]]
            if len(t.rows) > max_rows:
                md.append(f"\n_... {len(t.rows) - max_rows} more rows_")
            md.append("")
        for title, body in rep.result.text_blocks:
            md += [f"**{title}**\n", "```text", body, "```", ""]
        if rep.result.artifacts:
            md += ["Files written: " + ", ".join(f"`{a}`" for a in rep.result.artifacts)]
    elif rep.status == "needs_input":
        md.append(f"The agent asks: *{rep.clarification.message}*")
    else:
        md.append(f"Failed: {rep.error}" + (f"  \nHint: {rep.error_hint}" if rep.error_hint else ""))
    return "\n".join(md)


def _default(o: Any):
    if isinstance(o, Decimal):
        return float(o)
    if isinstance(o, (date, datetime)):
        return o.isoformat()
    if isinstance(o, Path):
        return str(o)
    if isinstance(o, set):
        return sorted(o)
    return str(o)


def to_dict(resp: AgentResponse) -> dict:
    d: dict[str, Any] = {"request": resp.request, "kind": resp.kind, "message": resp.message}
    if resp.route:
        r = resp.route
        d["routing"] = {"workflow_id": r.workflow_id, "method": r.method, "confidence": r.confidence, "reason": r.reason,
                        "note": r.note, "candidates": r.candidates}
    if resp.report:
        rep = resp.report
        d["run"] = {
            "run_id": rep.run_id, "workflow_id": rep.workflow_id, "workflow_name": rep.workflow_name, "status": rep.status,
            "duration_ms": round(rep.duration_ms, 1), "parameters": rep.params, "parameter_sources": rep.param_sources,
            "steps": [{"index": s.index, "name": s.name, "status": s.status, "duration_ms": round(s.duration_ms, 1),
                       "detail": s.detail, "error": s.error} for s in rep.steps],
            "decisions": [{"step": x.step, "name": x.name, "outcome": x.outcome, "detail": x.detail} for x in rep.decisions],
            "tool_calls": [{"tool": c.tool, "operation": c.operation, "step": c.step, "status": c.status, "attempts": c.attempts,
                            "duration_ms": round(c.duration_ms, 1), "error": c.error} for c in rep.tool_calls],
            "warnings": rep.warnings, "error": rep.error, "error_hint": rep.error_hint,
            "clarification": rep.clarification.message if rep.clarification else None,
            "result": ({"summary": rep.result.summary, "data": rep.result.data, "artifacts": rep.result.artifacts,
                        "tables": [{"title": t.title, "columns": t.columns, "rows": t.rows} for t in rep.result.tables],
                        "text_blocks": [{"title": a, "body": b} for a, b in rep.result.text_blocks]} if rep.result else None)}
    return d


def render_json(resp: AgentResponse) -> str:
    return json.dumps(to_dict(resp), indent=2, default=_default, ensure_ascii=False)
