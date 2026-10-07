"""WF003 - Vendor File Processing.

Rule (from Excel): rows missing SKU or product name are invalid.
Other problems (non-numeric price, duplicate SKU) are reported as warnings but do not
invalidate a row, because the Excel rule only names SKU and product name.
"""
from __future__ import annotations

from ..core.errors import NeedMoreInput, StepError, ToolError
from ..core.models import Param, Table
from ..core.registry import WorkflowModule
from ..utils import is_blank, map_columns, snake, to_decimal
from .common import describe_rows, file_extractor, source_note

CANONICAL = {
    "sku": ["item_code", "item_no", "item_number", "product_code", "part_no", "part_number", "vendor_sku",
            "article", "article_number", "code", "item_id", "product_id"],
    "product_name": ["name", "product_title", "title", "item_name", "description", "product", "item_description"],
    "price": ["cost_price", "unit_price", "cost", "wholesale_price", "unit_cost", "vendor_price"],
    "quantity": ["qty", "qty_available", "on_hand", "stock", "available", "quantity_available", "units"],
    "brand": ["manufacturer", "vendor", "supplier", "make"],
    "category": ["product_category", "type", "department"],
}
REQUIRED = ["sku", "product_name"]

wf = WorkflowModule(
    "WF003",
    params=[Param("vendor_file", "Vendor CSV or XLSX file to process", type="file",
                  sample_default="data/vendor_file.csv", extractor=file_extractor("csv", "xlsx", "xlsm"))],
    routing_hints=["vendor file", "vendor spreadsheet", "supplier file", "clean the file", "invalid rows",
                   "normalize columns", "supplier data", "process spreadsheet"],
)


@wf.step("Read file")
def read_file(ctx):
    path = ctx.param("vendor_file")
    if not path:
        raise NeedMoreInput("Which vendor file should I process? Give me a CSV or XLSX path.", ["vendor_file"])
    try:
        table = ctx.call_tool("excel_csv_parser", op="read", path=str(path), header_hints=CANONICAL)
    except ToolError as exc:
        raise StepError(f"Could not read the vendor file: {exc.message}",
                        hint="Supported formats: .csv, .xlsx, .xlsm") from exc
    if not table["rows"]:
        raise StepError(f"{table['source']} has headers but no data rows.")
    ctx.state["table"] = table
    extra = f", skipped {table['preamble_rows']} preamble row(s) above the header" if table["preamble_rows"] else ""
    sheet = f" (sheet '{table['sheet']}')" if table.get("sheet") else ""
    return (f"Read {len(table['rows'])} data row(s) from {source_note(ctx, 'vendor_file', table['source'])}{sheet}"
            f"{extra}; {table['blank_rows']} blank row(s) ignored")


@wf.step("detect columns")
def detect(ctx):
    headers = ctx.state["table"]["headers"]
    mapping = map_columns(headers, CANONICAL)
    unmapped = [h for h in headers if h not in mapping.values()]
    ctx.state["mapping"], ctx.state["unmapped"] = mapping, unmapped
    missing = [c for c in REQUIRED if c not in mapping]
    ctx.decide("required columns present", "yes" if not missing else f"missing: {', '.join(missing)}",
               "required: SKU and product name")
    if missing:
        raise StepError(f"Cannot find the required column(s): {', '.join(missing)}.",
                        hint=f"Columns found: {', '.join(headers)}. Rename a column or extend CANONICAL aliases.")
    pretty = ", ".join(f"{h} -> {c}" for c, h in mapping.items())
    return f"Detected {len(mapping)} known column(s): {pretty}" + (f"; kept as-is: {', '.join(unmapped)}" if unmapped else "")


@wf.step("normalize column names")
def normalize(ctx):
    mapping = ctx.state["mapping"]
    reverse = {actual: canon for canon, actual in mapping.items()}
    rows = []
    for r in ctx.state["table"]["rows"]:
        rec = {"_row": r["_row"]}
        for header, value in r.items():
            if header == "_row":
                continue
            name = reverse.get(header) or snake(header)
            rec[name] = "" if is_blank(value) else " ".join(str(value).split())
        rows.append(rec)
    ctx.state["rows"] = rows
    ctx.state["columns"] = [c for c in dict.fromkeys(list(reverse.values()) + [snake(h) for h in ctx.state["unmapped"]])]
    return f"Normalized to: {', '.join(ctx.state['columns'])}"


@wf.step("validate required fields")
def validate(ctx):
    result = ctx.call_tool("data_validation", op="required_fields", rows=ctx.state["rows"], required=REQUIRED)
    ctx.state["valid"], ctx.state["invalid"] = result["valid"], result["invalid"]
    dupes = ctx.call_tool("data_validation", op="duplicate_keys", rows=ctx.state["valid"], key="sku")
    ctx.state["duplicates"] = dupes
    if dupes:
        ctx.warn("Duplicate SKU(s) kept (not invalid per the rules): " +
                 describe_rows([f"{k} (rows {', '.join(map(str, v))})" for k, v in dupes.items()]))
    if "price" in ctx.state["columns"]:
        bad_price = ctx.call_tool("data_validation", op="numeric_fields", rows=ctx.state["valid"], fields=["price"])
        ctx.state["bad_price"] = bad_price
        if bad_price:
            ctx.warn("Non-numeric price in row(s): " +
                     describe_rows([f"{b['row']} ('{b['value']}')" for b in bad_price]) + " - rows kept, price blanked")
    ctx.decide("row invalid if SKU or product name is missing", f"{len(ctx.state['invalid'])} invalid of {len(ctx.state['rows'])}")
    return f"{len(ctx.state['valid'])} valid, {len(ctx.state['invalid'])} invalid"


@wf.step("identify invalid rows")
def identify(ctx):
    ctx.state["invalid_report"] = [
        {"source_row": x["row"]["_row"], "sku": x["row"].get("sku", ""), "product_name": x["row"].get("product_name", ""),
         "reasons": "; ".join(x["reasons"])} for x in ctx.state["invalid"]]
    return f"Built invalid-row report ({len(ctx.state['invalid_report'])} row(s))"


@wf.step("produce cleaned dataset")
def produce(ctx):
    cols = ctx.state["columns"]
    bad_price_rows = {b["row"] for b in ctx.state.get("bad_price", [])}
    cleaned = []
    for r in ctx.state["valid"]:
        rec = {c: r.get(c, "") for c in cols}
        if "price" in rec:
            dec = to_decimal(rec["price"])
            rec["price"] = f"{dec:.2f}" if dec is not None and r["_row"] not in bad_price_rows else ""
        if "quantity" in rec:
            q = to_decimal(rec["quantity"])
            rec["quantity"] = str(int(q)) if q is not None and q == q.to_integral() else rec["quantity"]
        if "sku" in rec:
            rec["sku"] = rec["sku"].upper()
        cleaned.append(rec)
    cleaned_path = ctx.write_artifact("vendor_cleaned.csv", cleaned, cols)
    inv_cols = ["source_row", "sku", "product_name", "reasons"]
    invalid_path = ctx.write_artifact("vendor_invalid_rows.csv", ctx.state["invalid_report"], inv_cols)

    total = len(ctx.state["rows"])
    summary = (f"Processed {total} row(s): {len(cleaned)} valid, {len(ctx.state['invalid_report'])} invalid "
               f"({ctx.state['table']['blank_rows']} blank row(s) ignored).")
    tables = [Table("Validation summary", ["Metric", "Value"], [
        ["Rows read", total], ["Valid rows", len(cleaned)], ["Invalid rows", len(ctx.state["invalid_report"])],
        ["Blank rows ignored", ctx.state["table"]["blank_rows"]],
        ["Duplicate SKUs (kept)", len(ctx.state["duplicates"])],
        ["Rows with non-numeric price", len(ctx.state.get("bad_price", []))]])]
    if ctx.state["invalid_report"]:
        tables.append(Table("Invalid rows", inv_cols,
                            [[r[c] or "(blank)" for c in inv_cols] for r in ctx.state["invalid_report"]]))
    preview_cols = cols[:6]
    tables.append(Table("Cleaned dataset (preview)", preview_cols, [[r[c] for c in preview_cols] for r in cleaned[:8]],
                        note=f"{len(cleaned)} row(s) in total; full file saved" if cleaned else ""))
    ctx.set_result(summary, tables=tables,
                   data={"total": total, "valid": len(cleaned), "invalid": ctx.state["invalid_report"],
                         "columns": cols, "duplicates": ctx.state["duplicates"]},
                   artifacts=[cleaned_path, invalid_path])
    return f"Wrote {cleaned_path} and {invalid_path}"
