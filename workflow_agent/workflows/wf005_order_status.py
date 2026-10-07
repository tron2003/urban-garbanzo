"""WF005 - Customer Order Status.

Rule (from Excel): if no order is found, ask for another identifier.
Accepts an order id (ORD-1001) or a customer email (which may return several orders).
The shipment API is retried on transient failure; if it stays down the order status is
still returned and the missing shipment data is clearly marked (graceful degradation).
"""
from __future__ import annotations

import re

from ..core.errors import NeedMoreInput, StepError, ToolError
from ..core.models import Param, Table
from ..core.registry import WorkflowModule

ORDER_RX = re.compile(r"\bORD[-\s_]?(\d{3,})\b", re.I)
EMAIL_RX = re.compile(r"[\w.+-]+@[\w-]+(?:\.[\w-]+)+")


def _order_extractor(text: str):
    m = ORDER_RX.search(text or "")
    return f"ORD-{m.group(1)}" if m else None


def _email_extractor(text: str):
    m = EMAIL_RX.search(text or "")
    return m.group(0) if m else None


wf = WorkflowModule(
    "WF005",
    params=[Param("order_id", "Order id such as ORD-1001", extractor=_order_extractor),
            Param("customer_email", "Customer email address (alternative to order id)", extractor=_email_extractor)],
    routing_hints=["order status", "where is my order", "where is order", "track order", "tracking", "shipment",
                   "has my order shipped", "delivery status", "customer order"],
)


@wf.step("Validate identifier")
def validate(ctx):
    order_id, email = ctx.param("order_id"), ctx.param("customer_email")
    if not order_id and not email:
        raise NeedMoreInput("Which order do you mean? Please give an order ID (like ORD-1001) or the customer's email.",
                            ["order_id"])
    if order_id:
        m = ORDER_RX.fullmatch(str(order_id).strip())
        if not m:
            raise NeedMoreInput(f"'{order_id}' is not a valid order ID (expected a format like ORD-1001). "
                                "Please check it, or give the customer's email instead.", ["order_id"])
        ctx.state["order_id"] = f"ORD-{m.group(1)}"
    if email:
        if not EMAIL_RX.fullmatch(str(email).strip()):
            if not order_id:
                raise NeedMoreInput(f"'{email}' does not look like a valid email address. "
                                    "Please re-enter it or give an order ID.", ["customer_email"])
        else:
            ctx.state["email"] = str(email).strip().lower()
    ctx.decide("identifier type", "order id" if ctx.state.get("order_id") else "customer email")
    return f"Using {ctx.state.get('order_id') or ctx.state.get('email')}"


@wf.step("search order data")
def search(ctx):
    try:
        res = ctx.call_tool("order_api", op="search", order_id=ctx.state.get("order_id"), email=ctx.state.get("email"))
    except ToolError as exc:
        raise StepError(f"The order system is unavailable: {exc.message}", hint="Try again in a moment.") from exc
    ident = ctx.state.get("order_id") or ctx.state.get("email")
    if res["count"] == 0:
        ctx.decide("order found", "no", f"nothing matches {ident}")
        raise NeedMoreInput(f"I couldn't find any order for {ident}. Could you double-check it or give me another "
                            "identifier (order ID or the email used at checkout)?",
                            ["order_id" if ctx.state.get("order_id") else "customer_email"])
    ctx.state["orders"] = res["orders"]
    ctx.decide("order found", "yes", f"{res['count']} order(s) for {ident}")
    return f"Found {res['count']} order(s)"


@wf.step("retrieve order status")
def status(ctx):
    ctx.state["summaries"] = [{"order": o, "status": o["status"]} for o in ctx.state["orders"]]
    return ", ".join(f"{o['order_id']}: {o['status']}" for o in ctx.state["orders"])


@wf.step("retrieve shipment information")
def shipment(ctx):
    notes = []
    for s in ctx.state["summaries"]:
        oid, st = s["order"]["order_id"], s["status"]
        s["shipment"], s["shipment_note"] = None, ""
        if st in ("Processing", "Pending"):
            s["shipment_note"] = "Not shipped yet - tracking will be available once the order leaves the warehouse."
        elif st == "Cancelled":
            s["shipment_note"] = "Order was cancelled - no shipment."
        else:
            try:
                s["shipment"] = ctx.call_tool("shipment_lookup", order_id=oid)
                if s["shipment"] is None:
                    s["shipment_note"] = "No shipment record found yet."
            except ToolError as exc:
                s["shipment_note"] = "Shipment information is temporarily unavailable (carrier lookup failed)."
                ctx.warn(f"{oid}: shipment lookup failed after retries ({exc.message}); status returned without tracking")
                ctx.decide("shipment lookup failed", "degraded response", f"{oid}: returning order status only")
        notes.append(f"{oid}: " + ("tracking found" if s["shipment"] else "no tracking"))
    return "; ".join(notes)


@wf.step("summarize current status")
def summarize(ctx):
    lines, item_rows, ship_rows = [], [], []
    for s in ctx.state["summaries"]:
        o, sh = s["order"], s["shipment"]
        line = f"{o['order_id']} is {o['status'].lower()}"
        if sh:
            line += f" - {sh['status'].lower()} via {sh['carrier']} (tracking {sh['tracking_number']}), ETA {sh['eta']}"
        elif s["shipment_note"]:
            line += f". {s['shipment_note']}"
        lines.append(line)
        for it in o["items"]:
            item_rows.append([o["order_id"], it["name"], it["sku"], it["qty"]])
        ship_rows.append([o["order_id"], o["status"], sh["carrier"] if sh else "-", sh["tracking_number"] if sh else "-",
                          sh["status"] if sh else "-", sh["eta"] if sh else "-", sh["last_event"] if sh else s["shipment_note"]])
    ctx.set_result(
        " | ".join(lines) + ".",
        tables=[Table("Order status & shipment", ["Order", "Status", "Carrier", "Tracking #", "Shipment", "ETA", "Last event / note"], ship_rows),
                Table("Items", ["Order", "Item", "SKU", "Qty"], item_rows)],
        data={"orders": [{"order_id": s["order"]["order_id"], "status": s["order"]["status"],
                          "shipment": s["shipment"], "shipment_note": s["shipment_note"]} for s in ctx.state["summaries"]]})
    return f"Summarized {len(lines)} order(s)"
