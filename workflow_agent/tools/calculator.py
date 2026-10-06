"""Exact decimal arithmetic. Money and percentages never go through binary floats,
so a 10.00% difference is exactly 10.00% (and therefore NOT 'more than 10%')."""
from __future__ import annotations

import math
from decimal import Decimal, ROUND_HALF_UP, getcontext
from typing import Any, Optional

from ..core.errors import ToolError
from ..utils import to_decimal
from .registry import tool

getcontext().prec = 28
_Q2 = Decimal("0.01")


def _d(v: Any) -> Optional[Decimal]:
    return v if isinstance(v, Decimal) else to_decimal(v)


@tool("calculator", aliases=("calculator",), description="Vectorised decimal calculator.")
def calculator(svc, op: str, **kw) -> Any:
    if op == "percent_difference":
        # pairs: [(base, other)] -> [(abs_pct, signed_pct) | None]; base is the denominator
        out = []
        for base, other in kw["pairs"]:
            b, o = _d(base), _d(other)
            if b is None or o is None or b == 0:
                out.append(None)
                continue
            signed = ((o - b) / b * 100).quantize(_Q2, ROUND_HALF_UP)
            out.append((abs(signed), signed))
        return out
    if op == "shortfall_ceiling":
        # pairs: [(target, current)] -> whole units needed to reach target (>= 0)
        out = []
        for target, current in kw["pairs"]:
            t, c = _d(target), _d(current)
            out.append(None if t is None or c is None else max(0, math.ceil(t - c)))
        return out
    if op == "rate":
        part, total = _d(kw["part"]), _d(kw["total"])
        if part is None or total is None or total == 0:
            return Decimal("0.00")
        return (part / total * 100).quantize(_Q2, ROUND_HALF_UP)
    if op == "mean":
        vals = [v for v in (_d(x) for x in kw["values"]) if v is not None]
        return (sum(vals) / len(vals)).quantize(_Q2, ROUND_HALF_UP) if vals else Decimal("0.00")
    if op == "multiply":
        a, b = _d(kw["a"]), _d(kw["b"])
        if a is None or b is None:
            raise ToolError("calculator", "multiply needs numeric operands")
        return a * b
    raise ToolError("calculator", f"unsupported op '{op}'")
