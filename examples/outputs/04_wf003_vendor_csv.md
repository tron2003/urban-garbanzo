### Request

> Process this vendor spreadsheet and show invalid rows.

**Selected workflow:** `WF003` - Vendor File Processing  
**Routing:** heuristic (confidence 0.65) - matched: spreadsheet, invalid, rows, proces  
**Parameters:** `vendor_file=data/vendor_file.csv` *(bundled sample)*

**Steps executed**

1. **success** - Read file - Read 8 data row(s) from vendor_file.csv (bundled sample data); 1 blank row(s) ignored
2. **success** - detect columns - Detected 5 known column(s): Item Code -> sku, Product Title -> product_name, Cost Price -> price, Qty Available -> quantity, Brand -> brand
3. **success** - normalize column names - Normalized to: sku, product_name, price, quantity, brand
4. **success** - validate required fields - 6 valid, 2 invalid
5. **success** - identify invalid rows - Built invalid-row report (2 row(s))
6. **success** - produce cleaned dataset - Wrote examples/outputs/artifacts/20261007-072100-64c029/vendor_cleaned.csv and examples/outputs/artifacts/20261007-072100-64c029/vendor_invalid_rows.csv

**Conditions / decisions**

- required columns present: **yes** (required: SKU and product name)
- row invalid if SKU or product name is missing: **2 invalid of 8**

**Tools / API calls**

- excel_csv_parser.read x1 (1 ms)
- data_validation.required_fields x1 (0 ms)
- data_validation.duplicate_keys x1 (0 ms)
- data_validation.numeric_fields x1 (0 ms)

**Warnings**

- Duplicate SKU(s) kept (not invalid per the rules): V-001 (rows 2, 9)
- Non-numeric price in row(s): 8 ('abc') - rows kept, price blanked

**Result (success)**

Processed 8 row(s): 6 valid, 2 invalid (1 blank row(s) ignored).

_Validation summary_

| Metric | Value |
|---|---|
| Rows read | 8 |
| Valid rows | 6 |
| Invalid rows | 2 |
| Blank rows ignored | 1 |
| Duplicate SKUs (kept) | 1 |
| Rows with non-numeric price | 1 |

_Invalid rows_

| source_row | sku | product_name | reasons |
|---|---|---|---|
| 4 | (blank) | Thermal Socks | missing sku |
| 5 | V-004 | (blank) | missing product name |

_Cleaned dataset (preview)_

| sku | product_name | price | quantity | brand |
|---|---|---|---|---|
| V-001 | Wool Beanie | 12.50 | 100 | NordicWear |
| V-002 | Fleece Gloves | 9.99 | 50 | NordicWear |
| V-005 | Down Vest |  | 10 | NordicWear |
| V-007 | Rain Poncho |  | 25 | NordicWear |
| V-001 | Wool Beanie (duplicate listing) | 12.50 | 100 | NordicWear |
| V-009 | Trail Gaiters | 8.40 | 15 | NordicWear |

Files written: `examples/outputs/artifacts/20261007-072100-64c029/vendor_cleaned.csv`, `examples/outputs/artifacts/20261007-072100-64c029/vendor_invalid_rows.csv`