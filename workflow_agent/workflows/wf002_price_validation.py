"""WF002 - Product Price Validation.

Rule (from Excel): flag when the price difference exceeds 10%.
Percentage difference = |vendor - internal| / internal x 100 (internal price is the base),
rounded to 2 decimals; flagged only when STRICTLY greater than the threshold, so an
exact 10.00% difference is not flagged. Decimal arithmetic avoids float error (79.00 vs 71.10).
"""
from __future__ import annotations

from decimal import Decimal

from ..core.errors import NeedMoreInput, StepError
from ..core.models import Param, Table
from ..core.registry import WorkflowModule
from ..utils import map_columns, norm_sku, to_decimal
from .common import describe_rows, file_extractor, load_table, missing_columns_error, number_extractor

PRODUCT_ALIASES = {"sku": ["item_code", "product_code", "product_sku"],
                   "name": ["product_name", "title", "product"],
                   "price": ["internal_price", "our_price", "selling_price", "retail_price", "unit_price"]}
VENDOR_ALIASES = {"sku": ["item_code", "product_code", "vendor_sku", "part_number"],
                  "vendor_price": ["price", "cost", "cost_price", "wholesale_price", "unit_price", "vendor_cost"]}

wf = WorkflowModule(
    "WF002",
    params=[
        Param("product_file", "Internal product CSV (sku, name, price)", type="file",
              sample_default="data/products.csv", extractor=file_extractor("csv")),
        Param("vendor_file", "Vendor price list CSV (sku, vendor_price)", type="file",
              sample_default="data/vendor_prices.csv"),
        Param("threshold_pct", "Flag when the price difference exceeds this percentage", type="number",
              extractor=number_extractor(r"(?:more than|over|exceed(?:s|ing)?|above|greater than|>)\s*(\d+(?:\.\d+)?)\s*%",
                                         r"(\d+(?:\.\d+)?)\s*%")),
    ],
    routing_hints=["vendor price", "price differs", "price mismatch", "validate prices", "price check",
                   "supplier price", "compare prices", "price discrepancy"],
)


@wf.step("Load product prices")
def load_prices(ctx):
    prod = load_table(ctx, "csv_reader", "product_file", "product file")
    vend = load_table(ctx, "csv_reader", "vendor_file", "vendor price list")
    pc, vc = map_columns(prod["headers"], PRODUCT_ALIASES), map_columns(vend["headers"], VENDOR_ALIASES)
    if {"sku", "price"} - set(pc):
        raise missing_columns_error("product file", sorted({"sku", "price"} - set(pc)), prod["headers"])
    if {"sku", "vendor_price"} - set(vc):
        raise missing_columns_error("vendor price list", sorted({"sku", "vendor_price"} - set(vc)), vend["headers"])
    ctx.state["products"] = [{"sku": r[pc["sku"]].strip(), "name": (r.get(pc.get("name", ""), "") or "").strip(),
                              "price_raw": r[pc["price"]], "row": r["_row"]} for r in prod["rows"]]
    ctx.state["vendor"] = [{"sku": r[vc["sku"]].strip(), "price_raw": r[vc["vendor_price"]], "row": r["_row"]}
                           for r in vend["rows"]]
    return f"Loaded {len(ctx.state['products'])} internal and {len(ctx.state['vendor'])} vendor price rows"


@wf.step("match products by SKU")
def match(ctx):
    vendor_by_sku: dict[str, dict] = {}
    dupes = []
    for v in ctx.state["vendor"]:
        key = norm_sku(v["sku"])
        if key in vendor_by_sku:
            dupes.append(v["sku"])
        vendor_by_sku[key] = v                       # last price in the vendor list wins
    if dupes:
        ctx.warn(f"Vendor list repeats SKU(s): {describe_rows(sorted(set(dupes)))}; the last price was used")
    matched, internal_only = [], []
    used = set()
    for p in ctx.state["products"]:
        key = norm_sku(p["sku"])
        if key in vendor_by_sku:
            matched.append((p, vendor_by_sku[key]))
            used.add(key)
        else:
            internal_only.append(p)
    vendor_only = [v for k, v in vendor_by_sku.items() if k not in used]
    ctx.state.update(matched=matched, internal_only=internal_only, vendor_only=vendor_only)
    ctx.decide("SKU match", f"{len(matched)} matched, {len(internal_only)} internal-only, {len(vendor_only)} vendor-only",
               "SKUs compared case- and whitespace-insensitively")
    if not matched:
        raise StepError("No SKUs match between the product file and the vendor price list.",
                        hint="Check that both files use the same SKU format.")
    return f"{len(matched)} SKU(s) matched"


@wf.step("compare internal and vendor prices")
def compare(ctx):
    comparable, invalid = [], []
    for p, v in ctx.state["matched"]:
        internal, vendor = to_decimal(p["price_raw"]), to_decimal(v["price_raw"])
        if internal is None or vendor is None:
            invalid.append((p["sku"], f"vendor price '{v['price_raw']}'" if vendor is None else f"internal price '{p['price_raw']}'", "not a valid price"))
        elif internal <= 0:
            invalid.append((p["sku"], f"internal price {internal}", "must be greater than zero to compute a percentage"))
        else:
            comparable.append({"sku": p["sku"], "name": p["name"], "internal": internal, "vendor": vendor})
    ctx.state["comparable"], ctx.state["invalid"] = comparable, invalid
    if invalid:
        ctx.warn("Could not compare: " + "; ".join(f"{s} ({what} {why})" for s, what, why in invalid))
    if not comparable:
        raise StepError("None of the matched products has two valid prices to compare.")
    return f"{len(comparable)} comparable pair(s); {len(invalid)} skipped"


@wf.step("calculate percentage difference")
def percentage(ctx):
    rows = ctx.state["comparable"]
    results = ctx.call_tool("calculator", op="percent_difference",
                            pairs=[(r["internal"], r["vendor"]) for r in rows])
    for r, res in zip(rows, results):
        r["abs_pct"], r["signed_pct"] = res
    return "Percentage differences calculated (base = internal price)"


@wf.step("flag exceptions")
def flag(ctx):
    threshold = Decimal(str(ctx.param("threshold_pct", ctx.settings.price_diff_threshold_pct)))
    rows = ctx.state["comparable"]
    for r in rows:
        r["flagged"] = r["abs_pct"] > threshold
    flagged = sorted((r for r in rows if r["flagged"]), key=lambda r: -r["abs_pct"])
    at_limit = [r["sku"] for r in rows if r["abs_pct"] == threshold]
    ctx.decide("price difference > threshold", f"{len(flagged)} of {len(rows)} flagged",
               f"threshold {threshold}% (strictly greater than)")
    if at_limit:
        ctx.decide("difference exactly at threshold", "not flagged", ", ".join(at_limit))

    def direction(r):
        return "vendor higher" if r["signed_pct"] > 0 else "vendor lower"

    matched_rows = [[r["sku"], r["name"], f"{r['internal']:.2f}", f"{r['vendor']:.2f}",
                     f"{r['signed_pct']:+.2f}%", "EXCEPTION" if r["flagged"] else "ok"] for r in rows]
    exc_rows = [[r["sku"], r["name"], f"{r['internal']:.2f}", f"{r['vendor']:.2f}",
                 f"{r['abs_pct']:.2f}%", direction(r)] for r in flagged]
    tables = []
    if exc_rows:
        tables.append(Table(f"Exceptions (difference > {threshold}%)",
                            ["SKU", "Product", "Internal", "Vendor", "Difference", "Direction"], exc_rows))
    tables.append(Table("All matched products", ["SKU", "Product", "Internal", "Vendor", "Diff", "Result"], matched_rows))
    unmatched = [[p["sku"], "in product file only (no vendor price)"] for p in ctx.state["internal_only"]] + \
                [[v["sku"], "in vendor list only (unknown product)"] for v in ctx.state["vendor_only"]]
    if unmatched:
        tables.append(Table("Unmatched SKUs", ["SKU", "Issue"], unmatched))
    artifact = ctx.write_artifact("price_validation_report.csv",
                                  [{"sku": r["sku"], "name": r["name"], "internal_price": r["internal"],
                                    "vendor_price": r["vendor"], "difference_pct": r["signed_pct"],
                                    "flagged": r["flagged"]} for r in rows],
                                  ["sku", "name", "internal_price", "vendor_price", "difference_pct", "flagged"])
    ctx.set_result(
        f"{len(flagged)} of {len(rows)} matched products differ from the vendor price by more than {threshold}%.",
        tables=tables,
        data={"threshold_pct": float(threshold), "matched": len(rows),
              "exceptions": [{"sku": r["sku"], "difference_pct": float(r["signed_pct"])} for r in flagged],
              "unmatched_internal": [p["sku"] for p in ctx.state["internal_only"]],
              "unmatched_vendor": [v["sku"] for v in ctx.state["vendor_only"]],
              "not_comparable": [s for s, _, _ in ctx.state["invalid"]]},
        artifacts=[artifact])
    return f"{len(flagged)} exception(s) flagged"
