### Request

> Classify these keywords: buy denim jacket, how to wash denim, denim jacket men, nike official site

**Selected workflow:** `WF008` - SEO Keyword Classification  
**Routing:** heuristic (confidence 0.66) - matched: keyword, classify, <keywords found>  
**Parameters:** `keywords=['buy denim jacket', 'how to wash denim', 'denim jacket men', 'nike official site']`, `categories_file=data/categories.csv` *(bundled sample)*

**Steps executed**

1. **success** - Read keywords - Read 4 keyword(s) supplied in the request; no search volumes available
2. **success** - remove duplicates - 4 unique keyword(s); 0 duplicate(s) removed
3. **success** - classify search intent - 1 transactional, 1 commercial, 1 informational, 1 navigational
4. **success** - map keywords to categories - 3 of 4 keyword(s) mapped to a category
5. **success** - identify high-priority keywords - 1 high-priority keyword(s)
6. **success** - export results - Exported 4 row(s) to examples/outputs/artifacts/20261007-074003-a0b100/keyword_report.csv

**Conditions / decisions**

- duplicate keywords: **0 removed** (compared case-, spacing- and punctuation-insensitively; max volume kept)
- intent source: **rules: 4, llm: 0** (LLM is only used for low-confidence keywords)
- category mapping: **3 mapped, 1 uncategorized** (token overlap with category_terms)
- high priority: **1 keyword(s)** (score >= 1000 (volume x intent weight); unmapped capped at medium)

**Tools / API calls**

- llm_classifier.classify_intent x1 (0 ms)
- csv_reader.read x1 (1 ms)

**Warnings**

- 1 keyword(s) have a low-confidence intent label (bare product phrases default to 'commercial'). Configure an LLM to refine them.

**Result (success)**

Classified 4 unique keyword(s): 1 transactional, 1 commercial, 1 informational, 1 navigational; 1 high priority.

_Intent breakdown_

| Intent | Keywords |
|---|---|
| Transactional | 1 |
| Commercial | 1 |
| Informational | 1 |
| Navigational | 1 |

_High-priority keywords_

| Keyword | Searches | Intent | Category | Target page |
|---|---|---|---|---|
| buy denim jacket |  | transactional | Apparel | /collections/apparel |

_Keyword report_

| Keyword | Searches | Intent | Category | Priority | Target page |
|---|---|---|---|---|---|
| buy denim jacket |  | transactional | Apparel | high | /collections/apparel |
| denim jacket men |  | commercial | Apparel | medium | /collections/apparel |
| how to wash denim |  | informational | Apparel | low | /blog/how-to-wash-denim (new guide, link to /collections/apparel) |
| nike official site |  | navigational | Uncategorized | low | No matching page - review manually |

Files written: `examples/outputs/artifacts/20261007-074003-a0b100/keyword_report.csv`