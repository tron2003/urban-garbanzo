### Request

> Classify these keywords and map them to pages.

**Selected workflow:** `WF008` - SEO Keyword Classification  
**Routing:** heuristic (confidence 0.67) - matched: keyword, classify, page, map  
**Parameters:** `keywords_file=data/keywords.csv` *(bundled sample)*, `categories_file=data/categories.csv` *(bundled sample)*

**Steps executed**

1. **success** - Read keywords - Read 23 keyword(s) keywords.csv (bundled sample data)
2. **success** - remove duplicates - 22 unique keyword(s); 1 duplicate(s) removed
3. **success** - classify search intent - 5 transactional, 11 commercial, 5 informational, 1 navigational
4. **success** - map keywords to categories - 21 of 22 keyword(s) mapped to a category
5. **success** - identify high-priority keywords - 12 high-priority keyword(s)
6. **success** - export results - Exported 22 row(s) to examples/outputs/artifacts/20261007-072100-536a6f/keyword_report.csv

**Conditions / decisions**

- duplicate keywords: **1 removed** (compared case-, spacing- and punctuation-insensitively; max volume kept)
- intent source: **rules: 22, llm: 0** (LLM is only used for low-confidence keywords)
- category mapping: **21 mapped, 1 uncategorized** (token overlap with category_terms)
- high priority: **12 keyword(s)** (score >= 1000 (volume x intent weight); unmapped capped at medium)

**Tools / API calls**

- csv_reader.read x2 (1 ms)
- llm_classifier.classify_intent x1 (0 ms)

**Warnings**

- 7 keyword(s) have a low-confidence intent label (bare product phrases default to 'commercial'). Configure an LLM to refine them.

**Result (success)**

Classified 22 unique keyword(s): 5 transactional, 11 commercial, 5 informational, 1 navigational; 12 high priority.

_Intent breakdown_

| Intent | Keywords |
|---|---|
| Transactional | 5 |
| Commercial | 11 |
| Informational | 5 |
| Navigational | 1 |

_High-priority keywords_

| Keyword | Searches | Intent | Category | Target page |
|---|---|---|---|---|
| running shoes | 12000 | commercial | Footwear | /collections/footwear |
| yoga mat | 9900 | commercial | Fitness | /collections/fitness |
| leather wallet | 5400 | commercial | Accessories | /collections/accessories |
| best bluetooth speaker under 50 | 4100 | commercial | Electronics | /collections/electronics |
| best running shoes for flat feet | 3600 | commercial | Footwear | /collections/footwear |
| stainless steel water bottle | 3300 | commercial | Home | /collections/home |
| buy running shoes online | 2400 | transactional | Footwear | /collections/footwear |
| denim jacket men | 2700 | commercial | Apparel | /collections/apparel |
| cheap yoga mat | 2100 | transactional | Fitness | /collections/fitness |
| buy leather wallet for men | 1600 | transactional | Accessories | /collections/accessories |
| yoga mat review | 1300 | commercial | Fitness | /collections/fitness |
| water bottle near me | 1000 | transactional | Home | /collections/home |

_Keyword report_

| Keyword | Searches | Intent | Category | Priority | Target page |
|---|---|---|---|---|---|
| running shoes | 12000 | commercial | Footwear | high | /collections/footwear |
| yoga mat | 9900 | commercial | Fitness | high | /collections/fitness |
| leather wallet | 5400 | commercial | Accessories | high | /collections/accessories |
| best bluetooth speaker under 50 | 4100 | commercial | Electronics | high | /collections/electronics |
| best running shoes for flat feet | 3600 | commercial | Footwear | high | /collections/footwear |
| stainless steel water bottle | 3300 | commercial | Home | high | /collections/home |
| buy running shoes online | 2400 | transactional | Footwear | high | /collections/footwear |
| denim jacket men | 2700 | commercial | Apparel | high | /collections/apparel |
| cheap yoga mat | 2100 | transactional | Fitness | high | /collections/fitness |
| buy leather wallet for men | 1600 | transactional | Accessories | high | /collections/accessories |
| yoga mat review | 1300 | commercial | Fitness | high | /collections/fitness |
| water bottle near me | 1000 | transactional | Home | high | /collections/home |
| how to choose running shoes | 1900 | informational | Footwear | medium | /blog/how-to-choose-running-shoes (new guide, link to /collections/footwear) |
| bluetooth speaker discount code | 590 | transactional | Electronics | medium | /collections/electronics |
| denim jacket outfit ideas | 1400 | informational | Apparel | medium | /blog/denim-jacket-outfit-ideas (new guide, link to /collections/apparel) |
| wool scarf gift | 390 | commercial | Accessories | medium | /collections/accessories |
| how to clean a leather wallet | 720 | informational | Accessories | low | /blog/how-to-clean-a-leather-wallet (new guide, link to /collections/accessories) |
| nike running shoes official site | 880 | navigational | Footwear | low | / (homepage / brand page) |
| leather wallet vs fabric wallet | 320 | commercial | Accessories | low | /collections/accessories |
| how to remove odor from water bottle | 480 | informational | Home | low | /blog/how-to-remove-odor-from-water-bottle (new guide, link to /collections/home) |
| astrology compatibility | 150 | commercial | Uncategorized | low | No matching page - review manually |
| what is a tpe yoga mat | 260 | informational | Fitness | low | /blog/what-is-a-tpe-yoga-mat (new guide, link to /collections/fitness) |

Files written: `examples/outputs/artifacts/20261007-072100-536a6f/keyword_report.csv`