"""data_validation (row level) and text_validation (generated copy checks)."""
from __future__ import annotations

import re
from collections import defaultdict
from typing import Any, Optional

from ..core.errors import ToolError
from ..utils import is_blank, norm_sku, truncate_words
from .registry import tool


@tool("data_validation", aliases=("data validation",), description="Row-level validation helpers.")
def data_validation(svc, op: str, rows: list[dict], **kw) -> Any:
    if op == "required_fields":
        required: list[str] = kw["required"]
        valid, invalid = [], []
        for r in rows:
            missing = [f for f in required if is_blank(r.get(f))]
            if missing:
                invalid.append({"row": r, "reasons": [f"missing {m.replace('_', ' ')}" for m in missing]})
            else:
                valid.append(r)
        return {"valid": valid, "invalid": invalid}
    if op == "duplicate_keys":
        key = kw["key"]
        seen: dict[str, list[int]] = defaultdict(list)
        for r in rows:
            k = norm_sku(r.get(key))
            if k:
                seen[k].append(r.get("_row", 0))
        return {k: v for k, v in seen.items() if len(v) > 1}
    if op == "numeric_fields":
        from ..utils import to_decimal
        bad = []
        for r in rows:
            for f in kw["fields"]:
                if not is_blank(r.get(f)) and to_decimal(r.get(f)) is None:
                    bad.append({"row": r.get("_row", 0), "field": f, "value": r.get(f)})
        return bad
    raise ToolError("data_validation", f"unsupported op '{op}'")


@tool("text_validation", aliases=("text validation",), description="Checks on text (length, forbidden terms).")
def text_validation(svc, op: str, text: str = "", **kw) -> Any:
    if op == "check":
        issues = []
        if not (text or "").strip():
            issues.append("empty")
        limit: Optional[int] = kw.get("max_length")
        if limit and len(text) > limit:
            issues.append(f"too long ({len(text)} > {limit})")
        for term in kw.get("forbidden_terms", []):
            if re.search(rf"\b{re.escape(term)}\b", text, re.I):
                issues.append(f"mentions '{term}' which is not in the supplied product data")
        if re.search(r"\[[^\]]*\]|\{\{|\}\}", text):
            issues.append("contains unresolved placeholder text")
        return {"ok": not issues, "issues": issues}
    if op == "truncate":
        return truncate_words(text, int(kw["limit"]))
    raise ToolError("text_validation", f"unsupported op '{op}'")
