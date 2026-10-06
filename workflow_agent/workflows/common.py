"""Helpers shared by many workflows (loading, extraction, formatting)."""
from __future__ import annotations

import re
from typing import Callable, Optional

from ..core.errors import NeedMoreInput, StepError, ToolError
from ..core.models import Table


def file_extractor(*exts: str) -> Callable[[str], Optional[str]]:
    pattern = re.compile(r"([\w\-./\\:~]+\.(?:" + "|".join(exts) + r"))\b", re.I)

    def extract(text: str) -> Optional[str]:
        m = pattern.search(text or "")
        return m.group(1) if m else None
    return extract


def number_extractor(*patterns: str) -> Callable[[str], Optional[float]]:
    compiled = [re.compile(p, re.I) for p in patterns]

    def extract(text: str) -> Optional[float]:
        for rx in compiled:
            m = rx.search(text or "")
            if m:
                return float(m.group(1).replace(",", ""))
        return None
    return extract


def load_table(ctx, tool: str, param: str, label: str, **extra) -> dict:
    """Read the file named by ctx.param(param) through a tool, turning failures into clear StepErrors."""
    path = ctx.param(param)
    if not path:
        raise NeedMoreInput(f"Which {label} should I use? Please give a file path (e.g. data/<file>.csv).", [param])
    try:
        table = ctx.call_tool(tool, op="read", path=str(path), **extra)
    except ToolError as exc:
        raise StepError(f"Could not read the {label}: {exc.message}",
                        hint=f"Check the path, or pass a different file (parameter '{param}').") from exc
    if not table["rows"]:
        raise StepError(f"The {label} ({table['source']}) has a header but no data rows.")
    return table


def missing_columns_error(label: str, needed: list[str], headers: list[str]) -> StepError:
    return StepError(
        f"The {label} is missing required column(s): {', '.join(needed)}.",
        hint=f"Columns found: {', '.join(headers)}.")


def source_note(ctx, param: str, path: str) -> str:
    return f"{path} (bundled sample data)" if ctx.source(param) == "sample" else str(path)


def describe_rows(items: list[str], limit: int = 4) -> str:
    shown = ", ".join(items[:limit])
    return shown + (f" and {len(items) - limit} more" if len(items) > limit else "")


def simple_table(title: str, columns: list[str], rows: list[list], note: str = "") -> Table:
    return Table(title=title, columns=columns, rows=rows, note=note)
