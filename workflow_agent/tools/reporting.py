"""Generic reporting helpers: grouping, percentiles and top-N counts."""
from __future__ import annotations

import math
from collections import Counter, defaultdict
from typing import Any

from ..core.errors import ToolError
from .registry import tool


def _p95(values: list[float]) -> float:
    if not values:
        return 0.0
    s = sorted(values)
    return s[max(0, math.ceil(0.95 * len(s)) - 1)]


@tool("reporting", aliases=("reporting",), description="Aggregation helpers used to build reports.")
def reporting(svc, op: str, rows: list[dict], **kw) -> Any:
    if op == "group_stats":
        keys: list[str] = kw["keys"]
        value: str = kw["value"]
        groups: dict[tuple, list[float]] = defaultdict(list)
        for r in rows:
            v = r.get(value)
            if v is not None:
                groups[tuple(r.get(k) for k in keys)].append(float(v))
        return [dict(zip(keys, g)) | {"count": len(v), "mean": sum(v) / len(v), "max": max(v), "p95": _p95(v)}
                for g, v in groups.items()]
    if op == "top_counts":
        keys = kw["keys"]
        counter = Counter(tuple(r.get(k) for k in keys) for r in rows)
        return [dict(zip(keys, k)) | {"count": c} for k, c in counter.most_common(int(kw.get("n", 5)))]
    raise ToolError("reporting", f"unsupported op '{op}'")
