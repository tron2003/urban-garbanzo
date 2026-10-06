"""Product catalogue reader (canonical column mapping + selection)."""
from __future__ import annotations

from typing import Any, Optional

from ..core.errors import ToolError
from ..utils import is_blank, map_columns, norm_sku
from .files import csv_reader
from .registry import tool

PRODUCT_ALIASES = {
    "sku": ["item code", "product code", "item no", "sku code"],
    "name": ["product name", "title", "product title", "item name", "product_name"],
    "category": ["product category", "type"],
    "collection": ["collection name", "range"],
    "launch_status": ["status", "lifecycle"],
    "price": ["internal price", "retail price", "unit price", "selling price"],
    "material": ["fabric"],
    "color": ["colour"],
    "target_audience": ["audience", "target audience"],
}


@tool("product_data_reader", aliases=("product data reader",), description="Read and filter the product catalogue.")
def product_data_reader(svc, op: str = "select", path: str = "", skus: Optional[list[str]] = None,
                        collection: Optional[str] = None) -> dict[str, Any]:
    if op != "select":
        raise ToolError("product_data_reader", f"unsupported op '{op}'")
    table = csv_reader(svc, op="read", path=path)
    cols = map_columns(table["headers"], PRODUCT_ALIASES)
    if "sku" not in cols or "name" not in cols:
        raise ToolError("product_data_reader",
                        f"catalogue needs SKU and name columns (found: {', '.join(table['headers'])})")
    products = []
    for r in table["rows"]:
        products.append({canon: (r.get(actual) or "").strip() for canon, actual in cols.items()} | {"_row": r["_row"]})

    selected, how = products, "all products"
    if skus:
        wanted = {norm_sku(s) for s in skus}
        selected = [p for p in products if norm_sku(p["sku"]) in wanted]
        how = f"SKUs {', '.join(skus)}"
    elif collection:
        c = collection.strip().lower()
        if c in {"new", "latest", "upcoming", "new arrivals"} and "launch_status" in cols:
            selected = [p for p in products if p.get("launch_status", "").lower() == "new"]
            how = "launch_status = new"
        elif "collection" in cols:
            selected = [p for p in products if c in p.get("collection", "").lower()]
            how = f"collection contains '{collection}'"
        else:
            selected, how = [], f"collection '{collection}' (no collection column)"
    return {"products": selected, "total": len(products), "selection": how, "columns": cols}
