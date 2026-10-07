### Request

> What is the status of order ORD-1004?

**Selected workflow:** `WF005` - Customer Order Status  
**Routing:** heuristic (confidence 0.74) - matched: order, statu, ord, <order_id found>  
**Parameters:** `order_id=ORD-1004`

**Steps executed**

1. **success** - Validate identifier - Using ORD-1004
2. **success** - search order data - Found 1 order(s)
3. **success** - retrieve order status - ORD-1004: Shipped
4. **success** - retrieve shipment information - ORD-1004: tracking found
5. **success** - summarize current status - Summarized 1 order(s)

**Conditions / decisions**

- identifier type: **order id**
- order found: **yes** (1 order(s) for ORD-1004)

**Tools / API calls**

- order_api.search x1 (0 ms)
- shipment_lookup x1 (200 ms) - succeeded after retry (2 attempts)

**Result (success)**

ORD-1004 is shipped - out for delivery via UPS (tracking UPS-1Z999AA10123456784), ETA 2026-10-07.

_Order status & shipment_

| Order | Status | Carrier | Tracking # | Shipment | ETA | Last event / note |
|---|---|---|---|---|---|---|
| ORD-1004 | Shipped | UPS | UPS-1Z999AA10123456784 | Out for delivery | 2026-10-07 | Out for delivery - Mohali hub (2026-10-07) |

_Items_

| Order | Item | SKU | Qty |
|---|---|---|---|
| ORD-1004 | Bluetooth Speaker | SKU-1011 | 1 |
