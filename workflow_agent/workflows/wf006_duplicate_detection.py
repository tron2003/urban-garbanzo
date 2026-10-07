"""WF006 - Duplicate Product Detection.

Rules (from Excel): an exact SKU match is a DEFINITE duplicate; high attribute similarity is a
POSSIBLE duplicate. 'Exact' is evaluated after normalisation (case, spaces, punctuation), because
normalising SKUs is an explicit workflow step ('cat 004' and 'CAT-004' are the same SKU).

Variants are not duplicates: if both records state a different colour, size, brand or material
they are kept apart even when the names are almost identical (Red M vs Blue M T-shirt).
"""
from __future__ import annotations

from collections import defaultdict

from ..core.errors import StepError
from ..core.models import Param, Table
from ..core.registry import WorkflowModule
from ..utils import is_blank, map_columns, norm_sku, snake
from .common import file_extractor, load_table, missing_columns_error, source_note

ALIASES = {"sku": ["item_code", "product_code", "product_sku", "id"],
           "product_name": ["name", "title", "product", "product_title"],
           "brand": ["manufacturer", "make"], "category": ["product_category", "type"],
           "color": ["colour"], "size": [], "material": ["fabric"], "price": ["unit_price"]}
HARD_ATTRS = ["brand", "color", "size", "material"]       # conflicts here => variants, not duplicates
SOFT_ATTRS = ["category"]
POSSIBLE_MIN_NAME = 0.55
HIGH, MEDIUM = 0.85, 0.70
LEVEL_RANK = {"definite": 3, "high": 2, "medium": 1}

wf = WorkflowModule(
    "WF006",
    params=[Param("catalog_file", "Product catalogue CSV to scan for duplicates", type="file",
                  sample_default="data/catalog.csv", extractor=file_extractor("csv"))],
    routing_hints=["duplicate", "duplicates", "duplicated", "same product listed twice", "dedupe", "near duplicates",
                   "repeated products", "likely duplicate"],
)


def _tokens(value: str) -> set[str]:
    return set(snake(value).split("_")) - {""}


def _compatible(a: str, b: str) -> bool:
    ta, tb = _tokens(a), _tokens(b)
    return bool(ta) and bool(tb) and (ta <= tb or tb <= ta)      # 'Black' ~ 'Phantom Black'


@wf.step("Load products")
def load(ctx):
    table = load_table(ctx, "csv_database_reader", "catalog_file", "product catalogue")
    cols = map_columns(table["headers"], ALIASES)
    if "product_name" not in cols:
        raise missing_columns_error("product catalogue", ["product_name"], table["headers"])
    recs = []
    for r in table["rows"]:
        rec = {c: (r.get(cols[c]) or "").strip() for c in cols}
        rec["_row"] = r["_row"]
        if is_blank(rec.get("product_name")):
            ctx.warn(f"Row {r['_row']} skipped: no product name")
            continue
        recs.append(rec)
    if len(recs) < 2:
        raise StepError("Need at least two products to look for duplicates.")
    ctx.state.update(recs=recs, cols=cols)
    if "sku" not in cols:
        ctx.warn("No SKU column found - only attribute similarity can be used")
    return f"Loaded {len(recs)} products from {source_note(ctx, 'catalog_file', table['source'])}"


@wf.step("normalize names/SKUs")
def normalize(ctx):
    recs = ctx.state["recs"]
    token_lists = ctx.call_tool("text_similarity", op="normalize", texts=[r["product_name"] for r in recs])
    for r, toks in zip(recs, token_lists):
        r["tokens"] = toks
        r["sku_key"] = norm_sku(r.get("sku", ""))
    return f"Normalized {len(recs)} names into tokens and SKUs into comparable keys"


@wf.step("compare identifiers")
def compare_ids(ctx):
    recs = ctx.state["recs"]
    by_key: dict[str, list[int]] = defaultdict(list)
    for i, r in enumerate(recs):
        if r["sku_key"]:
            by_key[r["sku_key"]].append(i)
    edges: dict[tuple[int, int], dict] = {}
    for key, idxs in by_key.items():
        for a_pos in range(len(idxs)):
            for b_pos in range(a_pos + 1, len(idxs)):
                a, b = idxs[a_pos], idxs[b_pos]
                exact = recs[a]["sku"] == recs[b]["sku"]
                how = "same SKU" if exact else f"same SKU after normalisation ('{recs[a]['sku']}' = '{recs[b]['sku']}')"
                edges[(a, b)] = {"level": "definite", "score": 1.0, "matching": ["sku"], "conflicts": [], "why": how}
    ctx.state["edges"] = edges
    ctx.decide("exact SKU match", f"{len(edges)} definite duplicate pair(s)", "rule: exact (normalised) SKU match = definite")
    return f"{len(edges)} definite pair(s) from SKU comparison"


@wf.step("compare product attributes")
def compare_attrs(ctx):
    recs, edges = ctx.state["recs"], ctx.state["edges"]
    tokens = [r["tokens"] for r in recs]
    pairs = [p for p in ctx.call_tool("text_similarity", op="candidate_pairs", tokens=tokens) if p not in edges]
    scores = ctx.call_tool("text_similarity", op="score_pairs", tokens=tokens, pairs=pairs) if pairs else []
    possible, variants = 0, []
    for (a, b), sc in zip(pairs, scores):
        if sc["combined"] < POSSIBLE_MIN_NAME:
            continue
        ra, rb = recs[a], recs[b]
        matching, conflicts, compared = [], [], 0
        for attr in HARD_ATTRS + SOFT_ATTRS:
            va, vb = ra.get(attr, ""), rb.get(attr, "")
            if is_blank(va) or is_blank(vb):
                continue
            compared += 1
            if _compatible(va, vb):
                matching.append(attr)
            else:
                conflicts.append(attr)
        if any(c in HARD_ATTRS for c in conflicts):
            variants.append((a, b, conflicts))
            continue
        agreement = (len(matching) / compared) if compared else 0.5
        final = round(0.65 * sc["combined"] + 0.35 * agreement, 3)
        level = "high" if final >= HIGH else "medium" if final >= MEDIUM else None
        if level:
            possible += 1
            edges[(a, b)] = {"level": level, "score": final, "matching": ["name"] + matching, "conflicts": conflicts,
                             "why": f"name similarity {sc['combined']:.2f}; matching: {', '.join(matching) or 'none compared'}"}
    ctx.state["variants"] = variants
    ctx.decide("high attribute similarity", f"{possible} possible duplicate pair(s)",
               f"score >= {HIGH} high, >= {MEDIUM} medium; hard conflicts ({', '.join(HARD_ATTRS)}) = variants")
    if variants:
        ctx.decide("similar names but conflicting attributes", f"{len(variants)} pair(s) kept apart as variants",
                   "e.g. " + "; ".join(f"{recs[a]['product_name']} vs {recs[b]['product_name']} ({'/'.join(c)})"
                                       for a, b, c in variants[:2]))
    return f"Scored {len(pairs)} candidate pair(s): {possible} possible, {len(variants)} variant(s) excluded"


@wf.step("group likely duplicates")
def group(ctx):
    recs, edges = ctx.state["recs"], ctx.state["edges"]
    parent = list(range(len(recs)))

    def find(x):
        while parent[x] != x:
            parent[x] = parent[parent[x]]
            x = parent[x]
        return x

    for a, b in edges:
        parent[find(a)] = find(b)
    members: dict[int, list[int]] = defaultdict(list)
    for i in range(len(recs)):
        members[find(i)].append(i)
    groups = []
    for ids in members.values():
        if len(ids) < 2:
            continue
        gedges = {k: v for k, v in edges.items() if k[0] in ids}
        groups.append({"ids": sorted(ids), "edges": gedges})
    ctx.state["groups"] = groups
    return f"{len(groups)} duplicate group(s) covering {sum(len(g['ids']) for g in groups)} records"


@wf.step("assign confidence")
def confidence(ctx):
    recs = ctx.state["recs"]
    for g in ctx.state["groups"]:
        weakest = min(g["edges"].values(), key=lambda e: (LEVEL_RANK[e["level"]], e["score"]))
        g["level"], g["score"] = weakest["level"], weakest["score"]
    ctx.state["groups"].sort(key=lambda g: (-LEVEL_RANK[g["level"]], -g["score"], g["ids"][0]))
    member_rows, evidence_rows, data = [], [], []
    for n, g in enumerate(ctx.state["groups"], start=1):
        label = {"definite": "DEFINITE", "high": "POSSIBLE (high)", "medium": "POSSIBLE (medium)"}[g["level"]]
        for i in g["ids"]:
            r = recs[i]
            member_rows.append([f"G{n}", label, r.get("sku") or "-", r["product_name"], r.get("brand", ""), r.get("color", ""), r.get("size", "")])
        for (a, b), e in sorted(g["edges"].items()):
            evidence_rows.append([f"G{n}", recs[a]["product_name"], recs[b]["product_name"], e["level"], f"{e['score']:.2f}", e["why"]])
        data.append({"group": f"G{n}", "confidence": g["level"], "score": g["score"],
                     "records": [{"sku": recs[i].get("sku", ""), "name": recs[i]["product_name"]} for i in g["ids"]],
                     "evidence": [e["why"] for e in g["edges"].values()]})
    definite = sum(1 for g in ctx.state["groups"] if g["level"] == "definite")
    summary = (f"Found {len(data)} duplicate group(s) in {len(recs)} products: {definite} definite, {len(data) - definite} possible."
               if data else f"No duplicates found among {len(recs)} products.")
    tables = []
    if data:
        tables = [Table("Duplicate groups", ["Group", "Confidence", "SKU", "Product", "Brand", "Colour", "Size"], member_rows),
                  Table("Evidence", ["Group", "Record A", "Record B", "Level", "Score", "Why"], evidence_rows)]
    if ctx.state["variants"]:
        tables.append(Table("Kept apart as variants (not duplicates)", ["Record A", "Record B", "Differs in"],
                            [[recs[a]["product_name"], recs[b]["product_name"], ", ".join(c)] for a, b, c in ctx.state["variants"]]))
    artifact = ctx.write_artifact("duplicate_groups.csv",
                                  [{"group": r[0], "confidence": r[1], "sku": r[2], "product": r[3]} for r in member_rows],
                                  ["group", "confidence", "sku", "product"]) if member_rows else None
    ctx.set_result(summary, tables=tables, data={"groups": data, "scanned": len(recs)},
                   artifacts=[artifact] if artifact else [])
    return f"{len(data)} group(s) with confidence assigned"
