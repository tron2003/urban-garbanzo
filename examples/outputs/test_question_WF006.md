### Request

> Find likely duplicate products in the catalog.

**Selected workflow:** `WF006` - Duplicate Product Detection  
**Routing:** heuristic (confidence 0.61) - matched: duplicate, likely, catalog, find  
**Parameters:** `catalog_file=data/catalog.csv` *(bundled sample)*

**Steps executed**

1. **success** - Load products - Loaded 17 products from catalog.csv (bundled sample data)
2. **success** - normalize names/SKUs - Normalized 17 names into tokens and SKUs into comparable keys
3. **success** - compare identifiers - 2 definite pair(s) from SKU comparison
4. **success** - compare product attributes - Scored 134 candidate pair(s): 3 possible, 6 variant(s) excluded
5. **success** - group likely duplicates - 5 duplicate group(s) covering 10 records
6. **success** - assign confidence - 5 group(s) with confidence assigned

**Conditions / decisions**

- exact SKU match: **2 definite duplicate pair(s)** (rule: exact (normalised) SKU match = definite)
- high attribute similarity: **3 possible duplicate pair(s)** (score >= 0.85 high, >= 0.7 medium; hard conflicts (brand, color, size, material) = variants)
- similar names but conflicting attributes: **6 pair(s) kept apart as variants** (e.g. Cotton T-Shirt Red M vs Cotton T-Shirt Blue M (color); Cotton T-Shirt Red M vs Cotton T-Shirt Red L (size))

**Tools / API calls**

- csv_database_reader.read x1 (2 ms)
- text_similarity.normalize x1 (0 ms)
- text_similarity.candidate_pairs x1 (0 ms)
- text_similarity.score_pairs x1 (12 ms)

**Result (success)**

Found 5 duplicate group(s) in 17 products: 2 definite, 3 possible.

_Duplicate groups_

| Group | Confidence | SKU | Product | Brand | Colour | Size |
|---|---|---|---|---|---|---|
| G1 | DEFINITE | CAT-003 | Samsung Galaxy S22 256GB | Samsung | Phantom Black | 256GB |
| G1 | DEFINITE | CAT-003 | Galaxy S22 256 GB (Samsung) | Samsung | Phantom Black | 256GB |
| G2 | DEFINITE | CAT-004 | Cotton T-Shirt Red M | BasicCo | Red | M |
| G2 | DEFINITE | cat 004 | Basic Cotton Tee Red (M) | BasicCo | Red | M |
| G3 | POSSIBLE (high) | CAT-010 | Leather Wallet Brown | Heritage | Brown |  |
| G3 | POSSIBLE (high) | CAT-011 | Brown Leather Wallet | Heritage | Brown |  |
| G4 | POSSIBLE (high) | CAT-001 | Apple iPhone 13 128GB Black | Apple | Black | 128GB |
| G4 | POSSIBLE (high) | CAT-002 | iPhone 13 (128 GB) - Black | Apple | Black | 128GB |
| G5 | POSSIBLE (medium) | CAT-020 | Stainless Steel Water Bottle 750ml | Aqua | Silver | 750ml |
| G5 | POSSIBLE (medium) | CAT-021 | Aqua Stainless Water Bottle 750 ml | Aqua | Silver | 750ml |

_Evidence_

| Group | Record A | Record B | Level | Score | Why |
|---|---|---|---|---|---|
| G1 | Samsung Galaxy S22 256GB | Galaxy S22 256 GB (Samsung) | definite | 1.00 | same SKU |
| G2 | Cotton T-Shirt Red M | Basic Cotton Tee Red (M) | definite | 1.00 | same SKU after normalisation ('CAT-004' = 'cat 004') |
| G3 | Leather Wallet Brown | Brown Leather Wallet | high | 1.00 | name similarity 1.00; matching: brand, color, material, category |
| G4 | Apple iPhone 13 128GB Black | iPhone 13 (128 GB) - Black | high | 0.90 | name similarity 0.84; matching: brand, color, size, category |
| G5 | Stainless Steel Water Bottle 750ml | Aqua Stainless Water Bottle 750 ml | medium | 0.84 | name similarity 0.75; matching: brand, color, size, material, category |

_Kept apart as variants (not duplicates)_

| Record A | Record B | Differs in |
|---|---|---|
| Cotton T-Shirt Red M | Cotton T-Shirt Blue M | color |
| Cotton T-Shirt Red M | Cotton T-Shirt Red L | size |
| Cotton T-Shirt Blue M | Cotton T-Shirt Red L | color, size |
| Leather Wallet Brown | Black Leather Wallet | color |
| Brown Leather Wallet | Black Leather Wallet | color |
| Bluetooth Speaker Mini | Bluetooth Speaker Mini | brand |

Files written: `examples/outputs/artifacts/20261007-074002-bb0711/duplicate_groups.csv`