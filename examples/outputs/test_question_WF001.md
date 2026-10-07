### Request

> Which products need restocking?

**Selected workflow:** `WF001` - Inventory Restock Check  
**Routing:** heuristic (confidence 0.43) - matched: reorder, product  
**Parameters:** `inventory_file=data/inventory.csv` *(bundled sample)*

**Steps executed**

1. **success** - Load inventory - Loaded 12 rows from inventory.csv (bundled sample data); 2 invalid
2. **success** - compare current stock with minimum threshold - 6 product(s) below minimum
3. **success** - identify low-stock products - 6 low-stock product(s), most critical first
4. **success** - calculate reorder quantity - Reorder quantity computed for 6 product(s)
5. **success** - generate restock list - Restock list with 6 product(s) saved to examples/outputs/artifacts/20261007-074002-46cbe4/restock_list.csv

**Conditions / decisions**

- current_stock < minimum_stock: **6 of 10 products below minimum** (strictly less-than; basis: per-product minimum_stock)
- stock equal to minimum: **not flagged** (SKU-1005 at exactly the minimum)
- reorder target: **fallback used** (no valid max_stock for some products; target = 2 x minimum_stock)

**Tools / API calls**

- csv_reader.read x1 (4 ms)
- calculator.shortfall_ceiling x1 (0 ms)

**Warnings**

- 2 inventory row(s) skipped: SKU-1011 (current_stock 'abc' is not a number), SKU-1012 (minimum_stock is missing)

**Result (success)**

6 of 10 products need restocking (312 units to order in total).

_Products requiring restock_

| SKU | Product | Current stock | Minimum | Suggested reorder qty | Target basis |
|---|---|---|---|---|---|
| SKU-1004 | Leather Wallet | 0 | 15 | 60 | max_stock |
| SKU-1008 | Wool Scarf | 3 | 12 | 21 | 2 x minimum |
| SKU-1006 | Running Shoes (42) | 8 | 20 | 72 | max_stock |
| SKU-1001 | Classic Cotton T-Shirt (M) | 12 | 25 | 88 | max_stock |
| SKU-1003 | Denim Jacket | 5 | 10 | 35 | max_stock |
| SKU-1010 | Yoga Mat | 14 | 15 | 36 | max_stock |

Files written: `examples/outputs/artifacts/20261007-074002-46cbe4/restock_list.csv`