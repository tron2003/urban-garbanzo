### Request

> Find products where vendor price differs by more than 10%.

**Selected workflow:** `WF002` - Product Price Validation  
**Routing:** heuristic (confidence 0.77) - matched: price, differ, vendor, 10, <threshold_pct found>  
**Parameters:** `threshold_pct=10.0`, `product_file=data/products.csv` *(bundled sample)*, `vendor_file=data/vendor_prices.csv` *(bundled sample)*

**Steps executed**

1. **success** - Load product prices - Loaded 12 internal and 12 vendor price rows
2. **success** - match products by SKU - 11 SKU(s) matched
3. **success** - compare internal and vendor prices - 9 comparable pair(s); 2 skipped
4. **success** - calculate percentage difference - Percentage differences calculated (base = internal price)
5. **success** - flag exceptions - 3 exception(s) flagged

**Conditions / decisions**

- SKU match: **11 matched, 1 internal-only, 1 vendor-only** (SKUs compared case- and whitespace-insensitively)
- price difference > threshold: **3 of 9 flagged** (threshold 10.0% (strictly greater than))
- difference exactly at threshold: **not flagged** (SKU-1003)

**Tools / API calls**

- csv_reader.read x2 (2 ms)
- calculator.percent_difference x1 (0 ms)

**Warnings**

- Could not compare: SKU-1011 (vendor price 'N/A' not a valid price); SKU-1012 (internal price 0 must be greater than zero to compute a percentage)

**Result (success)**

3 of 9 matched products differ from the vendor price by more than 10.0%.

_Exceptions (difference > 10.0%)_

| SKU | Product | Internal | Vendor | Difference | Direction |
|---|---|---|---|---|---|
| SKU-1008 | Wool Scarf | 24.00 | 31.50 | 31.25% | vendor higher |
| SKU-1002 | Classic Cotton T-Shirt (L) | 19.99 | 22.99 | 15.01% | vendor higher |
| SKU-1004 | Leather Wallet | 45.00 | 39.00 | 13.33% | vendor lower |

_All matched products_

| SKU | Product | Internal | Vendor | Diff | Result |
|---|---|---|---|---|---|
| SKU-1001 | Classic Cotton T-Shirt (M) | 19.99 | 20.49 | +2.50% | ok |
| SKU-1002 | Classic Cotton T-Shirt (L) | 19.99 | 22.99 | +15.01% | EXCEPTION |
| SKU-1003 | Denim Jacket | 79.00 | 71.10 | -10.00% | ok |
| SKU-1004 | Leather Wallet | 45.00 | 39.00 | -13.33% | EXCEPTION |
| SKU-1005 | Canvas Tote Bag | 12.50 | 12.50 | +0.00% | ok |
| SKU-1006 | Running Shoes (42) | 89.90 | 95.00 | +5.67% | ok |
| SKU-1007 | Running Shoes (43) | 89.90 | 89.90 | +0.00% | ok |
| SKU-1008 | Wool Scarf | 24.00 | 31.50 | +31.25% | EXCEPTION |
| SKU-1010 | Yoga Mat | 29.00 | 26.50 | -8.62% | ok |

_Unmatched SKUs_

| SKU | Issue |
|---|---|
| SKU-1009 | in product file only (no vendor price) |
| SKU-9999 | in vendor list only (unknown product) |

Files written: `examples/outputs/artifacts/20261007-072100-c3df80/price_validation_report.csv`