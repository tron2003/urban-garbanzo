"""Employee / task database (CSV-backed simulation)."""
from __future__ import annotations

from typing import Any

from ..core.errors import ToolError
from ..utils import is_blank, map_columns, snake, to_decimal
from .files import csv_reader
from .registry import tool

SKILL_ALIASES = {"js": "javascript", "reactjs": "react", "react.js": "react", "node.js": "node", "nodejs": "node",
                 "postgres": "postgresql", "k8s": "kubernetes", "ts": "typescript", "py": "python"}


def canon_skill(name: str) -> str:
    s = str(name).strip().lower()
    return SKILL_ALIASES.get(s, s)


def parse_skills(raw: str) -> dict[str, int]:
    """'react:5;css:3;python' -> {'react': 5, 'css': 3, 'python': 3}  (default proficiency 3)."""
    skills: dict[str, int] = {}
    for part in str(raw or "").replace(",", ";").split(";"):
        part = part.strip()
        if not part:
            continue
        name, _, level = part.partition(":")
        try:
            lvl = max(1, min(5, int(level))) if level.strip() else 3
        except ValueError:
            lvl = 3
        skills[canon_skill(name)] = lvl
    return skills


@tool("employee_task_db", aliases=("Employee/task database",), description="Employees, skills and workload.")
def employee_task_db(svc, op: str = "employees", path: str = "") -> dict[str, Any]:
    if op != "employees":
        raise ToolError("employee_task_db", f"unsupported op '{op}'")
    table = csv_reader(svc, op="read", path=path)
    cols = map_columns(table["headers"], {
        "employee_id": ["id", "emp_id"], "name": ["employee", "employee_name", "full_name"],
        "role": ["title", "job_title"], "skills": ["skill_set", "skillset"],
        "capacity_hours": ["capacity_hours_per_week", "weekly_capacity", "capacity"],
        "current_load_hours": ["current_load", "load_hours", "assigned_hours", "workload"],
        "open_tasks": ["tasks", "open_task_count"], "status": ["availability"]})
    missing = [c for c in ("name", "skills", "capacity_hours", "current_load_hours") if c not in cols]
    if missing:
        raise ToolError("employee_task_db", f"employee file is missing column(s): {', '.join(missing)}")
    employees, invalid = [], []
    for r in table["rows"]:
        cap, load = to_decimal(r.get(cols["capacity_hours"])), to_decimal(r.get(cols["current_load_hours"]))
        if is_blank(r.get(cols["name"])) or cap is None or load is None:
            invalid.append(r["_row"])
            continue
        employees.append({
            "employee_id": r.get(cols.get("employee_id", ""), "") or r.get(cols["name"]),
            "name": r[cols["name"]].strip(), "role": (r.get(cols.get("role", ""), "") or "").strip(),
            "skills": parse_skills(r.get(cols["skills"], "")),
            "capacity_hours": float(cap), "current_load_hours": float(load),
            "open_tasks": int(to_decimal(r.get(cols.get("open_tasks", ""), 0)) or 0),
            "status": (r.get(cols.get("status", ""), "") or "active").strip().lower(),
        })
    return {"employees": employees, "invalid_rows": invalid, "source": table["source"]}
