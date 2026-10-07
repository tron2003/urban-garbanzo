"""WF009 - Employee Task Assignment.

Rule (from Excel): prefer employees with the required skills and available capacity;
escalate if no suitable employee exists.

'Suitable' means ALL of: active status, matches the requested role (if any), has every required skill,
and enough free capacity to do the estimated work before the deadline
(free weekly hours pro-rated by the working days left). Suitable employees are ranked by a weighted score
of skill proficiency and free capacity; urgent tasks weight capacity more. If nobody is suitable the
workflow does not guess: it recommends ESCALATION and lists the near-misses with the reason each fell short.
"""
from __future__ import annotations

import math
import re
from datetime import timedelta

from ..core.errors import NeedMoreInput, StepError, ToolError
from ..core.models import Param, Table
from ..core.registry import WorkflowModule
from ..utils import find_dates, parse_date
from ..tools.employee_db import canon_skill
from .common import file_extractor, kv_extractor, number_extractor, source_note

SAMPLE_TASK = ("Fix the checkout page bug in the React storefront: the pay button is unresponsive on mobile Safari. "
               "Likely a JavaScript event-handling issue.")
COMMON_SKILLS = ["python", "javascript", "typescript", "react", "angular", "vue", "node", "django", "fastapi", "flask", "java",
                 "spring", "c#", ".net", "go", "rust", "php", "laravel", "ruby", "rails", "sql", "postgresql", "mysql", "mongodb",
                 "redis", "docker", "kubernetes", "aws", "azure", "gcp", "terraform", "linux", "ci/cd", "git", "html", "css",
                 "sass", "tailwind", "figma", "ui design", "ux research", "testing", "selenium", "cypress", "api design", "graphql",
                 "machine learning", "data analysis", "pandas", "swift", "kotlin", "android", "ios", "seo", "copywriting"]
ROLE_WORDS = {"developer": "developer", "dev": "developer", "engineer": "engineer", "designer": "designer",
              "qa": "qa", "tester": "qa", "devops": "devops"}
WEEKDAYS = "monday|tuesday|wednesday|thursday|friday|saturday|sunday"


def _priority(text: str):
    t = (text or "").lower()
    if re.search(r"\b(urgent|critical|asap|high[- ]priority|top priority|immediately|emergency)\b", t):
        return "high"
    if re.search(r"\blow[- ]priority\b|\bwhen (?:you )?can\b|\bno rush\b", t):
        return "low"
    if re.search(r"\b(medium|normal)[- ]priority\b", t):
        return "medium"
    return None


def _role(text: str):
    for word, role in ROLE_WORDS.items():
        if re.search(rf"\b{word}s?\b", text or "", re.I):
            return role
    return None


def _deadline(text: str):
    kv = kv_extractor(["deadline", "due date", "due"], ["task", "skills", "priority", "hours"])(text)
    if kv:
        return kv
    m = re.search(rf"\b(?:by|due(?: on)?|before)\s+(tomorrow|today|in\s+\d+\s+days?|(?:next\s+)?(?:{WEEKDAYS})|\d{{4}}-\d{{2}}-\d{{2}})\b", text or "", re.I)
    if m:
        return m.group(1)
    ds = find_dates(text or "")
    return ds[0].isoformat() if ds else None


def _task(text: str):
    kv = kv_extractor(["task description", "task"], ["skills", "deadline", "priority", "hours", "due"])(text)
    if kv:
        return kv
    m = re.search(r"[\"\u201c](.{12,}?)[\"\u201d]", text or "")
    return m.group(1).strip() if m else None


wf = WorkflowModule(
    "WF009",
    params=[
        Param("task_description", "Description of the task to assign", type="string", sample_default=SAMPLE_TASK, extractor=_task),
        Param("required_skills", "Skills the task needs (optional; also detected from the description)", type="array",
              extractor=kv_extractor(["skills", "required skills", "skills needed", "needs"], ["task", "deadline", "priority", "hours"])),
        Param("role", "Restrict to a role, e.g. developer / designer / qa", extractor=_role),
        Param("priority", "high | medium | low", extractor=_priority),
        Param("deadline", "Deadline: date, 'tomorrow', 'in 3 days', weekday", extractor=_deadline),
        Param("estimated_hours", "Estimated effort in hours", type="number",
              extractor=number_extractor(r"(\d+(?:\.\d+)?)\s*(?:hours?|hrs?|h)\b")),
        Param("employees_file", "Employee roster CSV", type="file", sample_default="data/employees.csv", extractor=file_extractor("csv")),
    ],
    routing_hints=["assign task", "assign this", "who should", "best available", "task assignment", "delegate",
                   "allocate", "who can take", "give this task to"],
)


def _working_days(start, end) -> int:
    d, n = start, 0
    while d <= end:
        if d.weekday() < 5:
            n += 1
        d += timedelta(days=1)
    return max(n, 1)


@wf.step("Understand task requirements")
def understand(ctx):
    desc = (ctx.param("task_description") or "").strip()
    if not desc:
        raise NeedMoreInput("What is the task? Please describe it (and ideally the skills needed, priority and deadline).", ["task_description"])
    if not ctx.param("employees_file"):
        raise NeedMoreInput("Which employee roster should I use? Please give a CSV path (e.g. data/employees.csv).", ["employees_file"])
    try:
        roster = ctx.call_tool("employee_task_db", op="employees", path=str(ctx.param("employees_file")))
    except ToolError as exc:
        raise StepError(f"Could not load the employee data: {exc.message}", hint="Check the employees_file path.") from exc
    ctx.state["roster"] = roster
    vocab = {canon_skill(s) for e in roster["employees"] for s in e["skills"]} | set(COMMON_SKILLS)
    text = desc.lower()
    found = [s for s in sorted(vocab, key=len, reverse=True) if re.search(rf"(?<![\w]){re.escape(s)}(?![\w])", text)]
    explicit = [canon_skill(s) for s in (ctx.param("required_skills") or [])]
    required = list(dict.fromkeys(explicit + found))
    role = ctx.param("role")
    if not required and not role:
        raise NeedMoreInput("I couldn't tell which skills this task needs. Which skills (e.g. react, python) or role "
                            "(developer, designer, QA) should the assignee have?", ["required_skills"])
    priority = ctx.param("priority") or "medium"
    deadline = None
    if ctx.param("deadline"):
        deadline = parse_date(ctx.param("deadline"), ctx.today)
        if deadline is None:
            raise NeedMoreInput(f"I couldn't understand the deadline '{ctx.param('deadline')}'. Try a date like 2026-10-12, 'tomorrow' or 'in 3 days'.", ["deadline"])
        if deadline < ctx.today:
            raise NeedMoreInput(f"The deadline {deadline.isoformat()} is in the past. What is the correct deadline?", ["deadline"])
    hours = ctx.param("estimated_hours")
    assumed = hours is None
    hours = float(hours) if hours is not None else 8.0
    if assumed:
        ctx.warn("No effort estimate given - assumed 8 hours (one working day).")
    ctx.state.update(desc=desc, required=required, role=role, priority=priority, deadline=deadline, hours=hours,
                     working_days=_working_days(ctx.today, deadline) if deadline else None)
    ctx.decide("task requirements", f"skills: {', '.join(required) or 'none detected'}; role: {role or 'any'}; priority: {priority}",
               f"deadline {deadline.isoformat() if deadline else 'none'}; {hours:g}h" + (" (assumed)" if assumed else ""))
    src = " (bundled sample task)" if ctx.source("task_description") == "sample" else ""
    return f"Skills: {', '.join(required) or '-'}; priority {priority}; deadline {deadline.isoformat() if deadline else 'none'}; {hours:g}h{src}"


@wf.step("compare employee skills")
def compare_skills(ctx):
    s = ctx.state
    cands = []
    for e in s["roster"]["employees"]:
        reasons = []
        if e["status"] not in ("active", "available"):
            reasons.append(f"not available ({e['status'].replace('_', ' ')})")
        if s["role"] and s["role"] not in e["role"].lower():
            reasons.append(f"role '{e['role']}' does not match '{s['role']}'")
        have = [k for k in s["required"] if k in e["skills"]]
        missing = [k for k in s["required"] if k not in e["skills"]]
        if missing:
            reasons.append("missing skill(s): " + ", ".join(missing))
        prof = (sum(e["skills"][k] for k in have) / (5 * len(s["required"]))) if s["required"] and have else 0.0
        cands.append(dict(e) | {"missing": missing, "coverage": len(have) / len(s["required"]) if s["required"] else 1.0,
                               "skill_score": round(prof if s["required"] else 0.5, 3), "reasons": reasons})
    s["cands"] = cands
    full = sum(1 for c in cands if not c["missing"])
    ctx.decide("skill match", f"{full} of {len(cands)} employees have every required skill", f"required: {', '.join(s['required']) or 'role only'}")
    if s["roster"]["invalid_rows"]:
        ctx.warn(f"{len(s['roster']['invalid_rows'])} employee row(s) in the roster were unreadable and ignored.")
    return f"{full} employee(s) cover all required skills"


@wf.step("check current workload")
def workload(ctx):
    s = ctx.state
    for c in s["cands"]:
        c["free"] = max(c["capacity_hours"] - c["current_load_hours"], 0.0)
        c["capacity_score"] = round(c["free"] / c["capacity_hours"], 3) if c["capacity_hours"] else 0.0
        usable = c["free"] * (s["working_days"] / 5.0) if s["working_days"] is not None else c["free"]
        c["usable"] = usable
        if usable + 1e-9 < s["hours"]:
            when = f" before {s['deadline'].isoformat()}" if s["deadline"] else ""
            c["reasons"].append(f"insufficient capacity: ~{usable:.1f}h available{when} vs {s['hours']:g}h needed")
    s["eligible"] = [c for c in s["cands"] if not c["reasons"]]
    ctx.decide("capacity check", f"{len(s['eligible'])} employee(s) suitable", "free hours (pro-rated to the deadline) >= estimated hours")
    return f"{len(s['eligible'])} suitable after workload check"


@wf.step("rank candidates")
def rank(ctx):
    s = ctx.state
    w_cap = 0.5 if s["priority"] == "high" else 0.4
    s["weights"] = {"skill_score": round(1 - w_cap, 2), "capacity_score": w_cap}
    if s["eligible"]:
        s["ranked"] = ctx.call_tool("ranking_logic", op="rank", items=s["eligible"],
                                    criteria=[{"key": "skill_score", "weight": 1 - w_cap}, {"key": "capacity_score", "weight": w_cap}],
                                    tie_breakers=["open_tasks", "name"])
    else:
        s["ranked"] = []
    ctx.decide("ranking weights", f"skills {s['weights']['skill_score']:.0%} / capacity {s['weights']['capacity_score']:.0%}",
               "urgent tasks weight free capacity more" if s["priority"] == "high" else "standard weighting")
    return f"Ranked {len(s['ranked'])} candidate(s)"


@wf.step("select employee")
def select(ctx):
    s = ctx.state
    if s["ranked"]:
        s["choice"] = s["ranked"][0]
        ctx.decide("assignee", f"{s['choice']['name']} ({s['choice']['role']})", f"score {s['choice']['_score']:.2f}")
        return f"Selected {s['choice']['name']}"
    s["choice"] = None
    near = sorted(s["cands"], key=lambda c: (-c["coverage"], len(c["reasons"]), -c["free"]))[:3]
    s["near"] = near
    ctx.decide("no suitable employee", "ESCALATE to manager", "nobody has all skills AND capacity")
    return "No suitable employee - escalating"


@wf.step("generate assignment summary")
def summary(ctx):
    s = ctx.state
    dl = s["deadline"].isoformat() if s["deadline"] else "none set"
    task_tbl = Table("Task", ["Item", "Detail"], [["Task", s["desc"]], ["Required skills", ", ".join(s["required"]) or "-"],
                                                  ["Role filter", s["role"] or "any"], ["Priority", s["priority"]],
                                                  ["Deadline", dl], ["Estimated effort", f"{s['hours']:g} h"]])
    if s["choice"]:
        c = s["choice"]
        skills_txt = ", ".join(f"{k} ({c['skills'][k]}/5)" for k in s["required"] if k in c["skills"]) or "role match"
        reasoning = (f"{c['name']} has {skills_txt}, {c['free']:.0f}h free this week "
                     f"({c['current_load_hours']:.0f}/{c['capacity_hours']:.0f}h booked, {c['open_tasks']} open task(s)), "
                     f"and scored highest ({c['_score']:.2f}) among {len(s['ranked'])} suitable candidate(s).")
        ranked_rows = [[i, r["name"], r["role"], f"{r['skill_score']:.2f}", f"{r['free']:.0f}h", f"{r['_score']:.2f}"] for i, r in enumerate(s["ranked"], 1)]
        tables = [Table("Recommended assignment", ["Item", "Detail"],
                        [["Employee", f"{c['name']} ({c['role']})"], ["Reasoning", reasoning], ["Priority", s["priority"]], ["Deadline", dl]]),
                  task_tbl, Table("Candidate ranking", ["#", "Name", "Role", "Skill score", "Free", "Total"], ranked_rows)]
        text = f"Assign to {c['name']} ({c['role']}). Priority {s['priority']}, deadline {dl}."
        data = {"decision": "assign", "employee": c["name"], "employee_id": c["employee_id"], "score": c["_score"],
                "priority": s["priority"], "deadline": dl, "reasoning": reasoning, "ranking": [r["name"] for r in s["ranked"]]}
    else:
        near_rows = [[c["name"], c["role"], "; ".join(c["reasons"])] for c in s["near"]]
        tables = [Table("Escalation required", ["Item", "Detail"], [
                      ["Decision", "No suitable employee - escalate to the manager"],
                      ["Why", "Nobody is active, has every required skill, and has enough free capacity"], ["Priority", s["priority"]], ["Deadline", dl]]),
                  task_tbl, Table("Closest candidates (not suitable)", ["Name", "Role", "Why not"], near_rows)]
        text = f"No suitable employee for this task - escalate to the manager. Priority {s['priority']}, deadline {dl}."
        data = {"decision": "escalate", "priority": s["priority"], "deadline": dl,
                "near_misses": [{"name": c["name"], "reasons": c["reasons"]} for c in s["near"]]}
    excluded = [[c["name"], c["role"], "; ".join(c["reasons"])] for c in s["cands"] if c["reasons"] and (not s["choice"] or c is not s["choice"])]
    if s["choice"] and excluded:
        tables.append(Table("Not suitable", ["Name", "Role", "Why not"], excluded))
    ctx.set_result(text, tables=tables, data=data)
    return text
