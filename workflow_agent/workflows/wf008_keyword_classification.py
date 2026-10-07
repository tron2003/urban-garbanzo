"""WF008 - SEO Keyword Classification.

Rule (from Excel): classify every keyword as informational, commercial, transactional or navigational.
Intent comes from deterministic rules first (cheap, explainable, reproducible); only low-confidence
keywords are sent to the LLM, and each row records which source decided ("rules" or "llm").

Priority = demand x commercial value of the intent, with a category requirement:
  weight: transactional 1.0, commercial 0.8, informational 0.4, navigational 0.3
  score = monthly_searches x weight  ->  high >= 1000, medium >= 300, otherwise low
  keywords that map to no category are capped at 'medium' (there is no page to send the visitor to).
When no search volume is supplied: transactional+category = high, commercial+category = medium, else low.
"""
from __future__ import annotations

import re

from ..core.errors import NeedMoreInput, StepError, ToolError
from ..core.models import Param, Table
from ..core.registry import WorkflowModule
from ..utils import is_blank, map_columns, snake, to_decimal
from .common import file_extractor, load_table, missing_columns_error, source_note

WEIGHT = {"transactional": 1.0, "commercial": 0.8, "informational": 0.4, "navigational": 0.3}
HIGH_SCORE, MEDIUM_SCORE = 1000, 300
KW_ALIASES = {"keyword": ["keywords", "query", "search_term", "search_query", "term", "phrase"],
              "volume": ["monthly_searches", "search_volume", "searches", "avg_monthly_searches", "monthly_volume"]}
CAT_ALIASES = {"category": ["name"], "category_terms": ["terms", "keywords", "category_keywords"],
               "target_page": ["page", "url", "landing_page"]}
GROUP = "keywords"


def _inline_keywords(text: str):
    """'Classify these keywords: a, b, c' (or one per line) -> list; None if no inline list is present."""
    if not re.search(r"\bkeywords?\b", text or "", re.I) or ":" not in text:
        return None
    body = text.split(":", 1)[1]
    items = [i.strip(" -*\u2022\"'") for i in re.split(r"[\n;,]", body)]
    items = [i for i in items if i]
    return items if len(items) >= 2 else None


wf = WorkflowModule(
    "WF008",
    params=[
        Param("keywords", "Keywords to classify, supplied inline (list)", type="array", sample_group=GROUP, extractor=_inline_keywords),
        Param("keywords_file", "Keyword CSV (keyword, optional monthly_searches)", type="file", sample_group=GROUP,
              sample_default="data/keywords.csv", extractor=file_extractor("csv")),
        Param("categories_file", "Category / page mapping CSV (category, category_terms, target_page)", type="file",
              sample_default="data/categories.csv"),
    ],
    routing_hints=["keyword", "keywords", "search intent", "seo keywords", "classify keywords", "keyword list",
                   "map keywords", "keyword research", "target page"],
)


def _norm_kw(text: str) -> str:
    return " ".join(re.sub(r"[^\w\s'-]", " ", str(text).lower()).split())


def _stem(tok: str) -> str:
    return tok[:-1] if len(tok) > 3 and tok.endswith("s") and not tok.endswith("ss") else tok


def _slug(text: str) -> str:
    return re.sub(r"[^a-z0-9]+", "-", text.lower()).strip("-")


@wf.step("Read keywords")
def read(ctx):
    inline = ctx.param("keywords")
    if inline:
        rows = [{"keyword": k, "volume": None, "row": i} for i, k in enumerate(inline, start=1)]
        origin = "supplied in the request"
    else:
        table = load_table(ctx, "csv_reader", "keywords_file", "keyword file")
        cols = map_columns(table["headers"], KW_ALIASES)
        if "keyword" not in cols:
            if len(table["headers"]) == 1:
                cols["keyword"] = table["headers"][0]
            else:
                raise missing_columns_error("keyword file", ["keyword"], table["headers"])
        rows = []
        for r in table["rows"]:
            kw = (r.get(cols["keyword"]) or "").strip()
            if is_blank(kw):
                continue
            vol = to_decimal(r.get(cols["volume"])) if "volume" in cols else None
            rows.append({"keyword": kw, "volume": float(vol) if vol is not None else None, "row": r["_row"]})
        origin = source_note(ctx, "keywords_file", table["source"])
    if not rows:
        raise NeedMoreInput("I didn't find any keywords. Paste a list (comma or line separated) or give a CSV path.", ["keywords"])
    ctx.state["rows"] = rows
    ctx.state["has_volume"] = any(r["volume"] is not None for r in rows)
    return f"Read {len(rows)} keyword(s) {origin}" + ("" if ctx.state["has_volume"] else "; no search volumes available")


@wf.step("remove duplicates")
def dedupe(ctx):
    merged: dict[str, dict] = {}
    for r in ctx.state["rows"]:
        key = _norm_kw(r["keyword"])
        if not key:
            continue
        if key in merged:
            m = merged[key]
            m["variants"] += 1
            if r["volume"] is not None and (m["volume"] is None or r["volume"] > m["volume"]):
                m["volume"] = r["volume"]        # variants overlap, so take the larger figure instead of summing
        else:
            merged[key] = {"keyword": key, "volume": r["volume"], "variants": 1}
    removed = len(ctx.state["rows"]) - len(merged)
    ctx.state["kws"] = list(merged.values())
    ctx.decide("duplicate keywords", f"{removed} removed", "compared case-, spacing- and punctuation-insensitively; max volume kept")
    return f"{len(merged)} unique keyword(s); {removed} duplicate(s) removed"


@wf.step("classify search intent")
def classify(ctx):
    res = ctx.call_tool("llm_classifier", op="classify_intent", keywords=[k["keyword"] for k in ctx.state["kws"]])
    for k, r in zip(ctx.state["kws"], res):
        k.update(intent=r["intent"], intent_confidence=r["confidence"], intent_source=r["source"])
    by_src = {s: sum(1 for k in ctx.state["kws"] if k["intent_source"] == s) for s in ("rules", "llm")}
    weak = sum(1 for k in ctx.state["kws"] if k["intent_confidence"] < 0.6)
    if weak:
        ctx.warn(f"{weak} keyword(s) have a low-confidence intent label (bare product phrases default to 'commercial'). "
                 + ("" if ctx.llm_available else "Configure an LLM to refine them."))
    ctx.decide("intent source", f"rules: {by_src['rules']}, llm: {by_src['llm']}", "LLM is only used for low-confidence keywords")
    counts = {i: sum(1 for k in ctx.state["kws"] if k["intent"] == i) for i in WEIGHT}
    return ", ".join(f"{n} {i}" for i, n in counts.items() if n)


@wf.step("map keywords to categories")
def map_categories(ctx):
    table = load_table(ctx, "csv_reader", "categories_file", "category mapping file")
    cols = map_columns(table["headers"], CAT_ALIASES)
    if {"category", "category_terms"} - set(cols):
        raise missing_columns_error("category mapping file", sorted({"category", "category_terms"} - set(cols)), table["headers"])
    cats = []
    for r in table["rows"]:
        terms = {_stem(t.strip().lower()) for t in re.split(r"[;|,]", r.get(cols["category_terms"], "")) if t.strip()}
        cats.append({"category": r[cols["category"]].strip(), "terms": terms, "page": (r.get(cols.get("target_page", ""), "") or "").strip()})
    mapped = 0
    for k in ctx.state["kws"]:
        toks = {_stem(t) for t in re.split(r"[\s-]+", k["keyword"])} | {_stem(k["keyword"].replace(" ", "").replace("-", ""))}
        best, best_hits = None, 0
        for c in cats:
            hits = len(toks & c["terms"])
            if hits > best_hits:
                best, best_hits = c, hits
        if best:
            mapped += 1
            k["category"], k["category_page"] = best["category"], best["page"]
        else:
            k["category"], k["category_page"] = "Uncategorized", ""
        # recommended page depends on intent: money keywords -> category page; informational -> guide content
        slug = _slug(k["keyword"])
        if not best:
            k["target_page"] = "No matching page - review manually"
        elif k["intent"] == "informational":
            k["target_page"] = f"/blog/{slug} (new guide, link to {best['page'] or best['category']})"
        elif k["intent"] == "navigational":
            k["target_page"] = "/ (homepage / brand page)"
        else:
            k["target_page"] = best["page"] or f"{best['category']} category page"
    ctx.decide("category mapping", f"{mapped} mapped, {len(ctx.state['kws']) - mapped} uncategorized", "token overlap with category_terms")
    return f"{mapped} of {len(ctx.state['kws'])} keyword(s) mapped to a category"


@wf.step("identify high-priority keywords")
def prioritise(ctx):
    for k in ctx.state["kws"]:
        mapped = k["category"] != "Uncategorized"
        if k["volume"] is not None:
            k["score"] = round(k["volume"] * WEIGHT[k["intent"]])
            k["priority"] = "high" if k["score"] >= HIGH_SCORE else "medium" if k["score"] >= MEDIUM_SCORE else "low"
        else:
            k["score"] = None
            k["priority"] = ("high" if k["intent"] == "transactional" else "medium" if k["intent"] == "commercial" else "low") if mapped else "low"
        if not mapped and k["priority"] == "high":
            k["priority"] = "medium"
    order = {"high": 0, "medium": 1, "low": 2}
    ctx.state["kws"].sort(key=lambda k: (order[k["priority"]], -(k["score"] or 0), k["keyword"]))
    high = [k for k in ctx.state["kws"] if k["priority"] == "high"]
    ctx.decide("high priority", f"{len(high)} keyword(s)", f"score >= {HIGH_SCORE} (volume x intent weight); unmapped capped at medium")
    return f"{len(high)} high-priority keyword(s)"


@wf.step("export results")
def export(ctx):
    kws = ctx.state["kws"]
    cols = ["keyword", "monthly_searches", "intent", "intent_source", "category", "priority", "recommended_target_page"]
    rows = [{"keyword": k["keyword"], "monthly_searches": "" if k["volume"] is None else int(k["volume"]), "intent": k["intent"],
             "intent_source": k["intent_source"], "category": k["category"], "priority": k["priority"],
             "recommended_target_page": k["target_page"]} for k in kws]
    artifact = ctx.write_artifact("keyword_report.csv", rows, cols)
    counts = {i: sum(1 for k in kws if k["intent"] == i) for i in WEIGHT}
    high = [k for k in kws if k["priority"] == "high"]
    tables = [Table("Intent breakdown", ["Intent", "Keywords"], [[i.capitalize(), n] for i, n in counts.items()])]
    if high:
        tables.append(Table("High-priority keywords", ["Keyword", "Searches", "Intent", "Category", "Target page"],
                            [[k["keyword"], "" if k["volume"] is None else int(k["volume"]), k["intent"], k["category"], k["target_page"]] for k in high]))
    tables.append(Table("Keyword report", ["Keyword", "Searches", "Intent", "Category", "Priority", "Target page"],
                        [[r["keyword"], r["monthly_searches"], r["intent"], r["category"], r["priority"], r["recommended_target_page"]] for r in rows]))
    ctx.set_result(f"Classified {len(kws)} unique keyword(s): {', '.join(f'{n} {i}' for i, n in counts.items() if n)}; {len(high)} high priority.",
                   tables=tables,
                   data={"keywords": [{"keyword": k["keyword"], "intent": k["intent"], "category": k["category"], "priority": k["priority"],
                                       "target_page": k["target_page"], "volume": k["volume"], "intent_source": k["intent_source"]} for k in kws],
                         "intent_counts": counts},
                   artifacts=[artifact])
    return f"Exported {len(rows)} row(s) to {artifact}"
