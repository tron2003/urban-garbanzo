### Request

> Show the orders for ana.silva@example.com

**Selected workflow:** `WF005` - Customer Order Status  
**Routing:** heuristic (confidence 0.47) - matched: order, <customer_email found>  
**Parameters:** `customer_email=ana.silva@example.com`

**Steps executed**

1. **success** - Validate identifier - Using ana.silva@example.com
2. **success** - search order data - Found 2 order(s)
3. **success** - retrieve order status - ORD-1001: Shipped, ORD-1006: Processing
4. **success** - retrieve shipment information - ORD-1001: tracking found; ORD-1006: no tracking
5. **success** - summarize current status - Summarized 2 order(s)

**Conditions / decisions**

- identifier type: **customer email**
- order found: **yes** (2 order(s) for ana.silva@example.com)

**Tools / API calls**

- order_api.search x1 (0 ms)
- shipment_lookup x1 (0 ms)

**Result (success)**

ORD-1001 is shipped - in transit via DHL (tracking DHL-7788123400), ETA 2026-10-10 | ORD-1006 is processing. Not shipped yet - tracking will be available once the order leaves the warehouse..

_Order status & shipment_

| Order | Status | Carrier | Tracking # | Shipment | ETA | Last event / note |
|---|---|---|---|---|---|---|
| ORD-1001 | Shipped | DHL | DHL-7788123400 | In transit | 2026-10-10 | Departed sorting hub - Frankfurt (2026-10-05) |
| ORD-1006 | Processing | - | - | - | - | Not shipped yet - tracking will be available once the order leaves the warehouse. |

_Items_

| Order | Item | SKU | Qty |
|---|---|---|---|
| ORD-1001 | Denim Jacket | SKU-1003 | 1 |
| ORD-1001 | Wool Scarf | SKU-1008 | 1 |
| ORD-1001 | Classic Cotton T-Shirt (M) | SKU-1001 | 1 |
| ORD-1006 | Stainless Water Bottle | SKU-1009 | 1 |
