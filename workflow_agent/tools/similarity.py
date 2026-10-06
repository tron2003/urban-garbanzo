"""Text similarity for duplicate detection (stdlib only: token Jaccard + difflib)."""
from __future__ import annotations

import re
from collections import defaultdict
from difflib import SequenceMatcher
from itertools import combinations
from typing import Any

from ..core.errors import ToolError
from .registry import tool

_STOP = {"the", "a", "an", "and", "with", "for", "of", "by", "in", "on", "new", "pack", "pcs", "pc"}
_UNIT = re.compile(r"(\d+(?:\.\d+)?)\s*(gb|tb|mb|ml|l|kg|g|cm|mm|oz|lb|inch|in)\b")


def normalize_text(text: str) -> list[str]:
    t = str(text or "").lower().replace("&", " and ")
    t = _UNIT.sub(r"\1\2", t)
    t = re.sub(r"[^a-z0-9.]+", " ", t)
    tokens = []
    for tok in t.split():
        tok = tok.strip(".")
        if not tok or tok in _STOP:
            continue
        if len(tok) > 3 and tok.endswith("s") and not tok.endswith("ss"):
            tok = tok[:-1]
        tokens.append(tok)
    return tokens


def score(a: list[str], b: list[str]) -> dict[str, float]:
    sa, sb = set(a), set(b)
    jac = len(sa & sb) / len(sa | sb) if sa | sb else 0.0
    seq = SequenceMatcher(None, " ".join(sorted(a)), " ".join(sorted(b))).ratio()
    return {"jaccard": round(jac, 3), "sequence": round(seq, 3), "combined": round(0.5 * jac + 0.5 * seq, 3)}


@tool("text_similarity", aliases=("text similarity",), description="Normalise names, propose candidate pairs, score pairs.")
def text_similarity(svc, op: str, **kw) -> Any:
    if op == "normalize":
        return [normalize_text(t) for t in kw["texts"]]
    if op == "candidate_pairs":
        token_lists: list[list[str]] = kw["tokens"]
        n = len(token_lists)
        if n <= 400:
            return list(combinations(range(n), 2))
        index: dict[str, list[int]] = defaultdict(list)       # inverted index keeps large catalogs sub-quadratic
        for i, toks in enumerate(token_lists):
            for t in set(toks):
                index[t].append(i)
        cap = max(20, n // 20)
        pairs: set[tuple[int, int]] = set()
        for ids in index.values():
            if len(ids) <= cap:
                pairs.update(combinations(ids, 2))
        return sorted(pairs)
    if op == "score_pairs":
        toks = kw["tokens"]
        return [score(toks[i], toks[j]) for i, j in kw["pairs"]]
    raise ToolError("text_similarity", f"unsupported op '{op}'")
