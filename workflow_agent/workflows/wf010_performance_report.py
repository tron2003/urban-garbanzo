"""WF010 - Workflow Performance Report.

Rule (from Excel): flag workflows with a failure rate above 10% or an average execution time above a defined threshold.

Definitions (stated so the numbers can be audited):
  * a run = all log rows sharing a run_id; its status is the logged run_status (or 'failed' if any step failed)
  * failure rate = failed runs / (successful + failed runs); 'needs_input' runs (the agent asked a question)
    are NOT failures and are excluded from the denominator
  * execution time of a run = sum of its step durations; average is over executed runs (success + failed)
  * thresholds (configurable via .env): failure rate > 10 %, workflow avg > 5000 ms, step avg > 2000 ms
"""
from __future__ import annotations

import re
from collections import defaultdict
from decimal import Decimal

from ..core.errors import StepError, ToolError
from ..core.models import Param, Table
from ..core.registry import WorkflowModule
from ..utils import is_blank, map_columns, to_decimal
from .common import file_extractor, load_table, missing_columns_error, source_note

ALIASES = {
    "workflow_id": ["workflow", "wf_id", "workflow_code"], "workflow_name": ["name"], "run_id": ["execution_id", "run", "trace_id"],
    "step_name": ["step", "task", "node"], "step_status": ["step_result"],
    "run_status": ["status", "result", "outcome", "execution_status"],
    "duration_ms": ["duration", "elapsed_ms", "execution_time_ms", "latency_ms", "time_ms"],
    "error_type": ["error_class", "exception"], "error_message": ["error", "message", "error_msg"], "timestamp": ["time", "started_at", "date"],
}
OK, FAIL, ASK = "success", "failed", "needs_input"


def _norm_status(v: str) -> str:
    s = (v or "").strip().lower()
    if s in ("success", "ok", "completed", "complete", "passed", "succeeded", "done"):
        return OK
    if s in ("failed", "fail", "error", "failure", "exception", "timeout"):
        return FAIL
    if s in ("needs_input", "needs input", "clarification", "waiting"):
        return ASK
    return s or "unknown"


wf = WorkflowModule(
    "WF010",
    params=[
        Param("log_file", "Execution log CSV", type="file", sample_default="data/execution_logs.csv", extractor=file_extractor("csv")),
        Param("live_logs", "Analyse this agent's own live execution log instead of the sample log", type="boolean",
              extractor=lambda t: True if re.search(r"\b(live|this agent'?s?|own|real|actual) (?:logs?|runs?|executions?)\b|\bour agent\b", t or "", re.I) else None),
    ],
    routing_hints=["performance report", "failing", "failure rate", "slow workflows", "success rate", "execution time",
                   "workflow performance", "which workflows", "errors most often", "frequent errors", "slowest"],
)


@wf.step("Load execution logs")
def load(ctx):
    if ctx.param("live_logs"):
        path = ctx.settings.log_file
        if not path.exists():
            raise StepError("There is no live execution log yet - run some workflows first.",
                            hint=f"Expected {path}. The agent writes it automatically after each run.")
        ctx.params["log_file"], ctx.param_sources["log_file"] = str(path), "user"
    table = load_table(ctx, "csv_database_reader", "log_file", "execution log")
    cols = map_columns(table["headers"], ALIASES)
    need = [c for c in ("workflow_id", "duration_ms") if c not in cols]
    if need:
        raise missing_columns_error("execution log", need, table["headers"])
    rows, bad = [], 0
    for i, r in enumerate(table["rows"]):
        dur = to_decimal(r.get(cols["duration_ms"]))
        wid = (r.get(cols["workflow_id"]) or "").strip()
        if dur is None or dur < 0 or not wid:
            bad += 1
            continue
        g = lambda k: (r.get(cols[k]) or "").strip() if k in cols else ""
        rows.append({"workflow_id": wid, "workflow_name": g("workflow_name"), "run_id": g("run_id") or f"row-{i}",
                     "step_name": g("step_name"), "step_status": _norm_status(g("step_status")) if "step_status" in cols else "",
                     "run_status": _norm_status(g("run_status")) if "run_status" in cols else "",
                     "duration_ms": float(dur), "error_type": g("error_type"), "error_message": g("error_message")})
    if bad:
        ctx.warn(f"{bad} log row(s) ignored (missing workflow id or invalid duration).")
    if not rows:
        raise StepError("The execution log has no usable rows.")
    ctx.state.update(rows=rows, step_level="step_name" in cols, names={r["workflow_id"]: r["workflow_name"] for r in rows if r["workflow_name"]})
    if not ctx.state["step_level"]:
        ctx.warn("The log has no step_name column, so per-step analysis (slow steps, error locations) is not possible.")
    return f"Loaded {len(rows)} log row(s) from {source_note(ctx, 'log_file', table['source'])}"


def _runs(ctx):
    runs: dict[str, dict] = {}
    for r in ctx.state["rows"]:
        run = runs.setdefault(r["run_id"], {"workflow_id": r["workflow_id"], "statuses": [], "run_status": "", "duration": 0.0})
        run["statuses"].append(r["step_status"])
        run["run_status"] = run["run_status"] or r["run_status"]
        run["duration"] += r["duration_ms"]
    for run in runs.values():
        if not run["run_status"] or run["run_status"] == "unknown":
            run["run_status"] = FAIL if FAIL in run["statuses"] else ASK if ASK in run["statuses"] else OK
    return runs


@wf.step("calculate success/failure rate")
def rates(ctx):
    runs = _runs(ctx)
    ctx.state["runs"] = runs
    stats: dict[str, dict] = defaultdict(lambda: {OK: 0, FAIL: 0, ASK: 0})
    for run in runs.values():
        stats[run["workflow_id"]][run["run_status"] if run["run_status"] in (OK, FAIL, ASK) else OK] += 1
    threshold = Decimal(str(ctx.settings.failure_rate_threshold_pct))
    for wid, s in stats.items():
        executed = s[OK] + s[FAIL]
        s["executed"], s["total"] = executed, executed + s[ASK]
        s["failure_rate"] = ctx.call_tool("calculator", op="rate", part=s[FAIL], total=executed)
        s["success_rate"] = (Decimal(100) - s["failure_rate"]) if executed else Decimal(0)
        s["fail_flag"] = s["failure_rate"] > threshold
    ctx.state["stats"] = dict(stats)
    flagged = [w for w, s in stats.items() if s["fail_flag"]]
    ctx.decide("failure rate > threshold", f"{len(flagged)} workflow(s) flagged: {', '.join(sorted(flagged)) or 'none'}",
               f"threshold {threshold}% (strictly greater); needs_input runs are not failures")
    total_fail = sum(s[FAIL] for s in stats.values())
    total_exec = sum(s["executed"] for s in stats.values())
    return f"{len(runs)} runs across {len(stats)} workflows; overall failure rate {ctx.call_tool('calculator', op='rate', part=total_fail, total=total_exec)}%"


@wf.step("calculate average execution time")
def avg_time(ctx):
    by_wf = defaultdict(list)
    for run in ctx.state["runs"].values():
        if run["run_status"] in (OK, FAIL):
            by_wf[run["workflow_id"]].append(run["duration"])
    threshold = ctx.settings.slow_workflow_threshold_ms
    for wid, s in ctx.state["stats"].items():
        s["avg_ms"] = ctx.call_tool("calculator", op="mean", values=by_wf.get(wid, []))
        s["slow_flag"] = float(s["avg_ms"]) > threshold
    slow = [w for w, s in ctx.state["stats"].items() if s["slow_flag"]]
    ctx.decide("avg execution time > threshold", f"{len(slow)} workflow(s) flagged: {', '.join(sorted(slow)) or 'none'}", f"threshold {threshold:g} ms")
    return f"Average run time computed for {len(by_wf)} workflow(s)"


@wf.step("identify frequent errors")
def errors(ctx):
    failed = [dict(r, error_message=re.sub(r"\d+", "#", r["error_message"]) or "(no message)", error_type=r["error_type"] or "(unknown)")
              for r in ctx.state["rows"] if r["step_status"] == FAIL or (not ctx.state["step_level"] and r["run_status"] == FAIL)]
    keys = ["workflow_id", "step_name", "error_type", "error_message"]
    ctx.state["top_errors"] = ctx.call_tool("reporting", op="top_counts", rows=failed, keys=keys, n=8) if failed else []
    ctx.state["failed_rows"] = failed
    return f"{len(failed)} failed step(s); {len(ctx.state['top_errors'])} distinct frequent error(s)"


@wf.step("identify slow steps")
def slow_steps(ctx):
    if not ctx.state["step_level"]:
        ctx.state["slow_steps"] = []
        return "Skipped: log has no step names"
    rows = [r for r in ctx.state["rows"] if r["step_status"] in (OK, FAIL) and r["step_name"]]
    stats = ctx.call_tool("reporting", op="group_stats", rows=rows, keys=["workflow_id", "step_name"], value="duration_ms")
    threshold = ctx.settings.slow_step_threshold_ms
    slow = sorted((s for s in stats if s["mean"] > threshold), key=lambda s: -s["mean"])
    ctx.state["slow_steps"] = slow
    ctx.decide("avg step time > threshold", f"{len(slow)} slow step(s)", f"threshold {threshold:g} ms")
    return f"{len(slow)} step(s) above {threshold:g} ms"


_ERR_ADVICE = [
    (r"timeout|timed out|unreachable|temporar", "add retries with exponential back-off and a graceful fallback for this dependency; review the timeout setting and add alerting"),
    (r"column|missing|required|schema|invalid|not a valid", "validate inputs earlier and return a specific correction message; add schema checks before this step runs"),
    (r"not found|unsupported|no such|empty", "pre-check that the file exists and has a supported type/content before starting the workflow, and tell the user what to supply"),
    (r"no .*match", "handle the empty-match case explicitly and ask the user for corrected input instead of failing"),
]
_SLOW_ADVICE = [
    (r"generate|create|llm|classif|messaging|description", "reduce LLM latency: shorter prompts, a smaller/faster model, cache repeated prompts, or run independent generation steps concurrently"),
    (r"compare|match|similar|group", "avoid all-pairs comparison: block candidates (inverted index / blocking keys) and vectorise the scoring"),
    (r"shipment|order|retriev|search|lookup|api", "cache lookups, set a tight timeout with retry, and call the dependency once per batch rather than per item"),
    (r"load|read|parse", "stream or cache file reads and avoid re-parsing the same file on every run"),
]


def _advice(rules, text: str, default: str) -> str:
    for rx, adv in rules:
        if re.search(rx, text, re.I):
            return adv
    return default


@wf.step("generate recommendations")
def recommend(ctx):
    s, names = ctx.state["stats"], ctx.state["names"]
    label = lambda w: f"{w} {names.get(w, '')}".strip()
    recs: list[str] = []
    for wid, st in sorted(s.items(), key=lambda kv: -kv[1]["failure_rate"]):
        if not st["fail_flag"]:
            continue
        top = next((e for e in ctx.state["top_errors"] if e["workflow_id"] == wid), None)
        if top:
            recs.append(f"[Reliability] {label(wid)} fails {st['failure_rate']}% of runs. Most frequent: '{top['error_message']}' in step "
                        f"'{top['step_name'] or 'n/a'}' ({top['count']}x) - " + _advice(_ERR_ADVICE, top["error_type"] + " " + top["error_message"], "investigate the root cause and add a regression test"))
        else:
            recs.append(f"[Reliability] {label(wid)} fails {st['failure_rate']}% of runs but the log has no error details - add error logging.")
    for wid, st in sorted(s.items(), key=lambda kv: -float(kv[1]["avg_ms"])):
        if st["slow_flag"]:
            steps = [x for x in ctx.state["slow_steps"] if x["workflow_id"] == wid]
            worst = steps[0] if steps else None
            recs.append(f"[Speed] {label(wid)} averages {float(st['avg_ms']):,.0f} ms per run (threshold {ctx.settings.slow_workflow_threshold_ms:,.0f}). "
                        + (f"Slowest step '{worst['step_name']}' averages {worst['mean']:,.0f} ms - " + _advice(_SLOW_ADVICE, worst["step_name"], "profile this step") if worst else "Add step timing to locate the bottleneck."))
    covered = {r.split(" ")[1] for r in recs if r.startswith("[Speed]")}
    for x in ctx.state["slow_steps"]:
        if x["workflow_id"] not in covered:
            recs.append(f"[Speed] {label(x['workflow_id'])}: step '{x['step_name']}' averages {x['mean']:,.0f} ms (p95 {x['p95']:,.0f}) - "
                        + _advice(_SLOW_ADVICE, x["step_name"], "profile this step"))
            covered.add(x["workflow_id"])
    if not recs:
        recs.append("No workflow exceeds the failure-rate or timing thresholds. Keep monitoring and re-run this report regularly.")

    ordered = sorted(s.items(), key=lambda kv: (-kv[1]["failure_rate"], kv[0]))
    metrics = [[w, names.get(w, ""), st["total"], st[OK], st[FAIL], st[ASK], f"{st['failure_rate']}%", f"{float(st['avg_ms']):,.0f}",
                ", ".join(f for f, on in (("HIGH FAILURE RATE", st["fail_flag"]), ("SLOW", st["slow_flag"])) if on) or "ok"]
               for w, st in ordered]
    tables = [Table("Workflow metrics (worst failure rate first)",
                    ["ID", "Workflow", "Runs", "OK", "Failed", "Asked user", "Failure rate", "Avg ms", "Flags"], metrics)]
    if ctx.state["top_errors"]:
        tables.append(Table("Most frequent errors", ["Workflow", "Step", "Error type", "Message", "Count"],
                            [[e["workflow_id"], e["step_name"] or "-", e["error_type"], e["error_message"], e["count"]] for e in ctx.state["top_errors"]]))
    if ctx.state["slow_steps"]:
        tables.append(Table(f"Slow steps (avg > {ctx.settings.slow_step_threshold_ms:,.0f} ms)", ["Workflow", "Step", "Avg ms", "p95 ms", "Runs"],
                            [[x["workflow_id"], x["step_name"], f"{x['mean']:,.0f}", f"{x['p95']:,.0f}", x["count"]] for x in ctx.state["slow_steps"][:10]]))
    flagged_fail = [w for w, st in ordered if st["fail_flag"]]
    flagged_slow = [w for w, st in s.items() if st["slow_flag"]]
    top3 = ", ".join(f"{w} ({st['failure_rate']}%)" for w, st in ordered[:3] if st["failure_rate"] > 0)
    summary = (f"{len(flagged_fail)} of {len(s)} workflows exceed the {ctx.settings.failure_rate_threshold_pct:g}% failure-rate threshold"
               + (f"; failing most often: {top3}" if top3 else "") + f". {len(flagged_slow)} workflow(s) exceed the average-time threshold.")
    artifact = ctx.write_artifact("performance_report.csv", [dict(zip(["workflow", "name", "runs", "ok", "failed", "asked_user", "failure_rate", "avg_ms", "flags"], m)) for m in metrics],
                                  ["workflow", "name", "runs", "ok", "failed", "asked_user", "failure_rate", "avg_ms", "flags"])
    ctx.set_result(summary, tables=tables, text_blocks=[("Recommendations", "\n".join(f"{i}. {r}" for i, r in enumerate(recs, 1)))],
                   data={"failure_flagged": flagged_fail, "slow_flagged": flagged_slow,
                         "metrics": {w: {"runs": st["total"], "failed": st[FAIL], "failure_rate": float(st["failure_rate"]), "avg_ms": float(st["avg_ms"])} for w, st in s.items()},
                         "recommendations": recs, "top_errors": ctx.state["top_errors"]},
                   artifacts=[artifact])
    return f"{len(recs)} recommendation(s)"
