"""Simulated order database + shipment API.

Real systems are unavailable, so these read JSON fixtures in data/. The shipment
API can simulate transient outages (a fixture row with "simulated_failures": N
fails its first N calls) so retry / graceful-degradation logic is exercised.
"""
from __future__ import annotations

import json
from typing import Any, Optional

from ..core.errors import ToolError, TransientToolError
from .registry import tool


def _fixture(svc, name: str) -> list[dict]:
    cache = svc.shared.setdefault("fixtures", {})
    if name not in cache:
        path = svc.settings.data_dir / name
        if not path.exists():
            raise ToolError("order_api", f"data source {name} is not available")
        try:
            cache[name] = json.loads(path.read_text(encoding="utf-8"))
        except json.JSONDecodeError as exc:
            raise ToolError("order_api", f"{name} is not valid JSON: {exc}") from exc
    return cache[name]


@tool("order_api", aliases=("Order database/API",), description="Look up orders by id or customer email.")
def order_api(svc, op: str = "search", order_id: Optional[str] = None, email: Optional[str] = None) -> dict[str, Any]:
    if op != "search":
        raise ToolError("order_api", f"unsupported op '{op}'")
    orders = _fixture(svc, "orders.json")
    if order_id:
        hits = [o for o in orders if o["order_id"].upper() == order_id.upper()]
    elif email:
        hits = [o for o in orders if o["customer_email"].lower() == email.lower()]
    else:
        raise ToolError("order_api", "order_id or email is required")
    return {"count": len(hits), "orders": hits}


@tool("shipment_lookup", aliases=("shipment lookup",), description="Carrier tracking for an order.")
def shipment_lookup(svc, order_id: str) -> Optional[dict[str, Any]]:
    shipments = _fixture(svc, "shipments.json")
    row = next((s for s in shipments if s["order_id"].upper() == order_id.upper()), None)
    if row is None:
        return None
    counters = svc.shared.setdefault("shipment_failures", {})
    allowed_failures = int(row.get("simulated_failures", 0))
    if counters.get(order_id, 0) < allowed_failures:
        counters[order_id] = counters.get(order_id, 0) + 1
        raise TransientToolError("shipment_lookup", "carrier API timed out (simulated)")
    return {k: v for k, v in row.items() if k != "simulated_failures"}
