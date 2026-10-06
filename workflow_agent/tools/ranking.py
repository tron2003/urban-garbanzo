"""Weighted ranking with explainable score breakdowns."""
from __future__ import annotations

from typing import Any

from ..core.errors import ToolError
from .registry import tool


@tool("ranking_logic", aliases=("ranking logic",), description="Weighted multi-criteria ranking.")
def ranking_logic(svc, op: str, items: list[dict], criteria: list[dict], tie_breakers: list[str] | None = None) -> list[dict]:
    """criteria: [{'key': 'skill_score', 'weight': 0.6}] where item[key] is already 0..1.
    Returns items sorted best-first with '_score' and '_breakdown' added. Ties are
    broken by tie_breakers (ascending), then by input order, so results are deterministic."""
    if op != "rank":
        raise ToolError("ranking_logic", f"unsupported op '{op}'")
    total_w = sum(float(c["weight"]) for c in criteria)
    if total_w <= 0:
        raise ToolError("ranking_logic", "criteria weights must sum to a positive number")
    ranked = []
    for order, item in enumerate(items):
        breakdown = {c["key"]: round(float(item.get(c["key"], 0.0)) * float(c["weight"]) / total_w, 4) for c in criteria}
        ranked.append(dict(item) | {"_score": round(sum(breakdown.values()), 4), "_breakdown": breakdown, "_order": order})
    ranked.sort(key=lambda x: (-x["_score"], *(x.get(k, 0) for k in (tie_breakers or [])), x["_order"]))
    return ranked
