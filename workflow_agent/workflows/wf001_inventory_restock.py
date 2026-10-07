"""WF001 - Inventory Restock Check.

Rule (from Excel): if current_stock < minimum_stock, mark the product for restock.
Equal stock is NOT flagged (strictly less than).
Reorder quantity = (max_stock, or minimum_stock x RESTOCK_TARGET_MULTIPLIER when max is absent) - current_stock.
"""
from __future__ import annotations

from ..core.errors import NeedMoreInput
from ..core.models import Param, Table
from ..core.registry import WorkflowModule
from ..utils import is_blank, map_columns, to_decimal
from .common import (describe_rows, file_extractor, load_table, missing_columns_error,
                     number_extractor, source_note)

ALIASES = {
    "sku": ["product_id", "item_code", "item", "product_sku"],
    "product_name": ["name", "product", "title", "description"],
    "category": [],
    "current_stock": ["stock", "quantity", "qty", "on_hand", "in_stock", "inventory", "current_qty"],
    "minimum_stock": ["min_stock", "minimum", "min", "reorder_level", "reorder_point", "threshold", "min_qty"],
    "max_stock": ["maximum_stock", "max", "target_stock", "max_qty", "par_level"],
}

wf = WorkflowModule(
    "WF001",
    params=[
        Param("inventory_file", "Path to the product inventory CSV", type="file",
              sample_default="data/inventory.csv", extractor=file_extractor("csv")),
        Param("threshold", "Optional minimum stock threshold applied to every product "
                           "(overrides the per-product minimum_stock column)", type="number",
              extractor=number_extractor(r"(?:below|under|less than|fewer than|threshold(?: of)?)\s+(\d+)")),
    ],
    routing_hints=["restock", "reorder", "running low", "low stock", "out of stock", "inventory levels",
                   "stock levels", "needs replenishing", "below minimum stock"],
)


@wf.step("Load inventory")
def load_inventory(ctx):
    table = load_table(ctx, "csv_reader", "inventory_file", "inventory file")
    cols = map_columns(table["headers"], ALIASES)
    threshold = ctx.param("threshold")
    needed = ["sku", "current_stock"] + ([] if threshold is not None else ["minimum_stock"])
    absent = [c for c in needed if c not in cols]
    if absent == ["minimum_stock"]:
        raise NeedMoreInput("The inventory file has no minimum-stock column. What minimum stock "
                            "threshold should I use for all products?", ["threshold"])
    if absent:
        raise missing_columns_error("inventory file", absent, table["headers"])

    good, bad = [], []
    for r in table["rows"]:
        sku = (r.get(cols["sku"]) or "").strip()
        stock = to_decimal(r.get(cols["current_stock"]))
        minimum = to_decimal(threshold) if threshold is not None else to_decimal(r.get(cols["minimum_stock"]))
        maximum = to_decimal(r.get(cols["max_stock"])) if "max_stock" in cols else None
        problem = None
        if not sku:
            problem = "missing SKU"
        elif stock is None:
            problem = f"current_stock '{r.get(cols['current_stock'])}' is not a number"
        elif stock < 0:
            problem = "current_stock is negative"
        elif minimum is None:
            problem = "minimum_stock is missing"
        if problem:
            bad.append(f"{sku or 'row ' + str(r['_row'])} ({problem})")
            continue
        good.append({"sku": sku, "product_name": (r.get(cols.get("product_name", ""), "") or sku).strip(),
                     "current_stock": stock, "minimum_stock": minimum, "max_stock": maximum})
    ctx.state.update(rows=good, skipped=bad, source=table["source"])
    if bad:
        ctx.warn(f"{len(bad)} inventory row(s) skipped: {describe_rows(bad, 5)}")
    if not good:
        from ..core.errors import StepError
        raise StepError("No valid inventory rows to evaluate.")
    return f"Loaded {len(table['rows'])} rows from {source_note(ctx, 'inventory_file', table['source'])}; {len(bad)} invalid"


@wf.step("compare current stock with minimum threshold")
def compare(ctx):
    flagged = 0
    for r in ctx.state["rows"]:
        r["below_minimum"] = r["current_stock"] < r["minimum_stock"]
        flagged += r["below_minimum"]
    basis = (f"global threshold {ctx.param('threshold'):g}" if ctx.param("threshold") is not None
             else "per-product minimum_stock")
    ctx.decide("current_stock < minimum_stock", f"{flagged} of {len(ctx.state['rows'])} products below minimum",
               f"strictly less-than; basis: {basis}")
    return f"{flagged} product(s) below minimum"


@wf.step("identify low-stock products")
def identify(ctx):
    low = [r for r in ctx.state["rows"] if r["below_minimum"]]
    low.sort(key=lambda r: (r["current_stock"] / r["minimum_stock"]) if r["minimum_stock"] else 0)
    ctx.state["low"] = low
    at_min = [r["sku"] for r in ctx.state["rows"] if r["current_stock"] == r["minimum_stock"]]
    if at_min:
        ctx.decide("stock equal to minimum", "not flagged", f"{', '.join(at_min)} at exactly the minimum")
    return f"{len(low)} low-stock product(s), most critical first"


@wf.step("calculate reorder quantity")
def reorder(ctx):
    mult = ctx.settings.restock_target_multiplier
    pairs, basis = [], []
    for r in ctx.state["low"]:
        if r["max_stock"] is not None and r["max_stock"] > r["minimum_stock"]:
            pairs.append((r["max_stock"], r["current_stock"]))
            basis.append("max_stock")
        else:
            pairs.append((r["minimum_stock"] * to_decimal(mult), r["current_stock"]))
            basis.append(f"{mult:g} x minimum")
    qty = ctx.call_tool("calculator", op="shortfall_ceiling", pairs=pairs) if pairs else []
    for r, q, b in zip(ctx.state["low"], qty, basis):
        r["reorder_qty"], r["target_basis"] = q, b
    if any(b != "max_stock" for b in basis):
        ctx.decide("reorder target", "fallback used",
                   f"no valid max_stock for some products; target = {mult:g} x minimum_stock")
    return f"Reorder quantity computed for {len(qty)} product(s)"


@wf.step("generate restock list")
def generate(ctx):
    low = ctx.state["low"]
    rows = [[r["sku"], r["product_name"], int(r["current_stock"]), int(r["minimum_stock"]),
             r["reorder_qty"], r["target_basis"]] for r in low]
    columns = ["SKU", "Product", "Current stock", "Minimum", "Suggested reorder qty", "Target basis"]
    artifact = ctx.write_artifact("restock_list.csv",
                                  [dict(zip(columns, row)) for row in rows], columns) if rows else None
    total_units = sum(r["reorder_qty"] for r in low)
    if low:
        summary = (f"{len(low)} of {len(ctx.state['rows'])} products need restocking "
                   f"({total_units} units to order in total).")
    else:
        summary = f"No products need restocking: all {len(ctx.state['rows'])} evaluated products are at or above minimum."
    ctx.set_result(summary,
                   tables=[Table("Products requiring restock", columns, rows)] if rows else [],
                   data={"restock": [{"sku": r["sku"], "current_stock": int(r["current_stock"]),
                                      "minimum_stock": int(r["minimum_stock"]), "reorder_qty": r["reorder_qty"]}
                                     for r in low],
                         "evaluated": len(ctx.state["rows"]), "skipped": ctx.state["skipped"]},
                   artifacts=[artifact] if artifact else [])
    return f"Restock list with {len(low)} product(s)" + (f" saved to {artifact}" if artifact else "")
