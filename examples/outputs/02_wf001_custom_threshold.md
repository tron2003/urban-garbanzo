### Request

> Which products have stock below 20 units?

**Selected workflow:** `WF001` - Inventory Restock Check  
**Routing:** heuristic (confidence 0.57) - matched: stock, below, product, <threshold found>  
**Parameters:** `threshold=20.0`, `inventory_file=data/inventory.csv` *(bundled sample)*

**Steps executed**

1. **success** - Load inventory - Loaded 12 rows from inventory.csv (bundled sample data); 1 invalid
2. **success** - compare current stock with minimum threshold - 7 product(s) below minimum
3. **success** - identify low-stock products - 7 low-stock product(s), most critical first
4. **success** - calculate reorder quantity - Reorder quantity computed for 7 product(s)
5. **success** - generate restock list - Restock list with 7 product(s) saved to examples/outputs/artifacts/20261007-074003-ed4556/restock_list.csv

**Conditions / decisions**

- current_stock < minimum_stock: **7 of 11 products below minimum** (strictly less-than; basis: global threshold 20)
- reorder target: **fallback used** (no valid max_stock for some products; target = 2 x minimum_stock)

**Tools / API calls**

- csv_reader.read x1 (1 ms)
- calculator.shortfall_ceiling x1 (0 ms)

**Warnings**

- 1 inventory row(s) skipped: SKU-1011 (current_stock 'abc' is not a number)

**Result (success)**

7 of 11 products need restocking (349 units to order in total).

_Products requiring restock_

| SKU | Product | Current stock | Minimum | Suggested reorder qty | Target basis |
|---|---|---|---|---|---|
| SKU-1004 | Leather Wallet | 0 | 20 | 60 | max_stock |
| SKU-1008 | Wool Scarf | 3 | 20 | 37 | 2 x minimum |
| SKU-1003 | Denim Jacket | 5 | 20 | 35 | max_stock |
| SKU-1006 | Running Shoes (42) | 8 | 20 | 72 | max_stock |
| SKU-1012 | Desk Lamp | 9 | 20 | 21 | max_stock |
| SKU-1001 | Classic Cotton T-Shirt (M) | 12 | 20 | 88 | max_stock |
| SKU-1010 | Yoga Mat | 14 | 20 | 36 | max_stock |

Files written: `examples/outputs/artifacts/20261007-074003-ed4556/restock_list.csv`