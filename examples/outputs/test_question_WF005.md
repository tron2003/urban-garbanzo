### Request

> Where is order ORD-1001?

**Selected workflow:** `WF005` - Customer Order Status  
**Routing:** heuristic (confidence 0.64) - matched: order, ord, 1001, <order_id found>  
**Parameters:** `order_id=ORD-1001`

**Steps executed**

1. **success** - Validate identifier - Using ORD-1001
2. **success** - search order data - Found 1 order(s)
3. **success** - retrieve order status - ORD-1001: Shipped
4. **success** - retrieve shipment information - ORD-1001: tracking found
5. **success** - summarize current status - Summarized 1 order(s)

**Conditions / decisions**

- identifier type: **order id**
- order found: **yes** (1 order(s) for ORD-1001)

**Tools / API calls**

- order_api.search x1 (0 ms)
- shipment_lookup x1 (0 ms)

**Result (success)**

ORD-1001 is shipped - in transit via DHL (tracking DHL-7788123400), ETA 2026-10-10.

_Order status & shipment_

| Order | Status | Carrier | Tracking # | Shipment | ETA | Last event / note |
|---|---|---|---|---|---|---|
| ORD-1001 | Shipped | DHL | DHL-7788123400 | In transit | 2026-10-10 | Departed sorting hub - Frankfurt (2026-10-05) |

_Items_

| Order | Item | SKU | Qty |
|---|---|---|---|
| ORD-1001 | Denim Jacket | SKU-1003 | 1 |
| ORD-1001 | Wool Scarf | SKU-1008 | 1 |
| ORD-1001 | Classic Cotton T-Shirt (M) | SKU-1001 | 1 |
