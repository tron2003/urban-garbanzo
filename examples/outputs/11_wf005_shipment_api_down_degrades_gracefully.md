### Request

> Where is order ORD-1007?

**Selected workflow:** `WF005` - Customer Order Status  
**Routing:** heuristic (confidence 0.60) - matched: order, ord, <order_id found>  
**Parameters:** `order_id=ORD-1007`

**Steps executed**

1. **success** - Validate identifier - Using ORD-1007
2. **success** - search order data - Found 1 order(s)
3. **success** - retrieve order status - ORD-1007: Shipped
4. **success** - retrieve shipment information - ORD-1007: no tracking
5. **success** - summarize current status - Summarized 1 order(s)

**Conditions / decisions**

- identifier type: **order id**
- order found: **yes** (1 order(s) for ORD-1007)
- shipment lookup failed: **degraded response** (ORD-1007: returning order status only)

**Tools / API calls**

- order_api.search x1 (0 ms)
- shipment_lookup x1 (601 ms) - FAILED: carrier API timed out (simulated)

**Warnings**

- ORD-1007: shipment lookup failed after retries (carrier API timed out (simulated)); status returned without tracking

**Result (success)**

ORD-1007 is shipped. Shipment information is temporarily unavailable (carrier lookup failed)..

_Order status & shipment_

| Order | Status | Carrier | Tracking # | Shipment | ETA | Last event / note |
|---|---|---|---|---|---|---|
| ORD-1007 | Shipped | - | - | - | - | Shipment information is temporarily unavailable (carrier lookup failed). |

_Items_

| Order | Item | SKU | Qty |
|---|---|---|---|
| ORD-1007 | Wool Scarf | SKU-1008 | 1 |
