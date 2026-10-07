### Request

> Where is order ORD-9999?

**Selected workflow:** `WF005` - Customer Order Status  
**Routing:** heuristic (confidence 0.60) - matched: order, ord, <order_id found>  
**Parameters:** `order_id=ORD-9999`

**Steps executed**

1. **success** - Validate identifier - Using ORD-9999
2. **needs_input** - search order data - _I couldn't find any order for ORD-9999. Could you double-check it or give me another identifier (order ID or the email used at checkout)?_
3. **skipped** - retrieve order status
4. **skipped** - retrieve shipment information
5. **skipped** - summarize current status

**Conditions / decisions**

- identifier type: **order id**
- order found: **no** (nothing matches ORD-9999)

**Tools / API calls**

- order_api.search x1 (0 ms)

**Result (needs_input)**

The agent asks: *I couldn't find any order for ORD-9999. Could you double-check it or give me another identifier (order ID or the email used at checkout)?*

---

### Request

> Sorry, it's ORD-1003

**Selected workflow:** `WF005` - Customer Order Status  
**Routing:** continued - your reply answers the question I asked  
**Parameters:** `order_id=ORD-1003`

**Steps executed**

1. **success** - Validate identifier - Using ORD-1003
2. **success** - search order data - Found 1 order(s)
3. **success** - retrieve order status - ORD-1003: Delivered
4. **success** - retrieve shipment information - ORD-1003: tracking found
5. **success** - summarize current status - Summarized 1 order(s)

**Conditions / decisions**

- identifier type: **order id**
- order found: **yes** (1 order(s) for ORD-1003)

**Tools / API calls**

- order_api.search x1 (0 ms)
- shipment_lookup x1 (0 ms)

**Result (success)**

ORD-1003 is delivered - delivered via FedEx (tracking FDX-5521009876), ETA 2026-09-19.

_Order status & shipment_

| Order | Status | Carrier | Tracking # | Shipment | ETA | Last event / note |
|---|---|---|---|---|---|---|
| ORD-1003 | Delivered | FedEx | FDX-5521009876 | Delivered | 2026-09-19 | Delivered to front desk (2026-09-19) |

_Items_

| Order | Item | SKU | Qty |
|---|---|---|---|
| ORD-1003 | Leather Wallet | SKU-1004 | 1 |
