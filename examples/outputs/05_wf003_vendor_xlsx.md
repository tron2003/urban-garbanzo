### Request

> Process the vendor file data/vendor_file.xlsx and show invalid rows.

**Selected workflow:** `WF003` - Vendor File Processing  
**Routing:** heuristic (confidence 0.70) - matched: file, vendor, invalid, rows  
**Parameters:** `vendor_file=data/vendor_file.xlsx`

**Steps executed**

1. **success** - Read file - Read 5 data row(s) from vendor_file.xlsx (sheet 'Price List'), skipped 3 preamble row(s) above the header; 0 blank row(s) ignored
2. **success** - detect columns - Detected 5 known column(s): Part No -> sku, Description -> product_name, Unit Price -> price, On Hand -> quantity, Manufacturer -> brand
3. **success** - normalize column names - Normalized to: sku, product_name, price, quantity, brand
4. **success** - validate required fields - 3 valid, 2 invalid
5. **success** - identify invalid rows - Built invalid-row report (2 row(s))
6. **success** - produce cleaned dataset - Wrote examples/outputs/artifacts/20261007-074003-74817f/vendor_cleaned.csv and examples/outputs/artifacts/20261007-074003-74817f/vendor_invalid_rows.csv

**Conditions / decisions**

- required columns present: **yes** (required: SKU and product name)
- row invalid if SKU or product name is missing: **2 invalid of 5**

**Tools / API calls**

- excel_csv_parser.read x1 (9 ms)
- data_validation.required_fields x1 (0 ms)
- data_validation.duplicate_keys x1 (0 ms)
- data_validation.numeric_fields x1 (0 ms)

**Result (success)**

Processed 5 row(s): 3 valid, 2 invalid (0 blank row(s) ignored).

_Validation summary_

| Metric | Value |
|---|---|
| Rows read | 5 |
| Valid rows | 3 |
| Invalid rows | 2 |
| Blank rows ignored | 0 |
| Duplicate SKUs (kept) | 0 |
| Rows with non-numeric price | 0 |

_Invalid rows_

| source_row | sku | product_name | reasons |
|---|---|---|---|
| 7 | (blank) | Snow Goggles | missing sku |
| 8 | NW-103 | (blank) | missing product name |

_Cleaned dataset (preview)_

| sku | product_name | price | quantity | brand |
|---|---|---|---|---|
| NW-100 | Merino Base Layer | 24.00 | 40 | NordicWear |
| NW-101 | Insulated Mittens | 15.50 | 25 | NordicWear |
| NW-104 | Hiking Poles |  | 18 | NordicWear |

Files written: `examples/outputs/artifacts/20261007-074003-74817f/vendor_cleaned.csv`, `examples/outputs/artifacts/20261007-074003-74817f/vendor_invalid_rows.csv`