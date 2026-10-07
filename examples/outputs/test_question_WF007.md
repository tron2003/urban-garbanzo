### Request

> Create a campaign brief for the new collection.

**Selected workflow:** `WF007` - Marketing Campaign Brief  
**Routing:** heuristic (confidence 0.78) - matched: campaign, brief, collection, create, <collection found>  
**Parameters:** `collection=new`, `products_file=data/products.csv` *(bundled sample)*

**Steps executed**

1. **needs_input** - Validate inputs - _Before I write the brief I need: campaign goal and campaign dates (start and end). For example: 'Goal: increase autumn sales, from 2026-11-01 to 2026-11-30'. Audience and promotion are optional._
2. **skipped** - identify campaign objective
3. **skipped** - summarize products
4. **skipped** - create messaging
5. **skipped** - create channel recommendations
6. **skipped** - create campaign checklist

**Conditions / decisions**

- goal and dates present: **no - asking before generating** (Excel rule: request missing goal/dates first)

**Tools / API calls**

- none

**Result (needs_input)**

The agent asks: *Before I write the brief I need: campaign goal and campaign dates (start and end). For example: 'Goal: increase autumn sales, from 2026-11-01 to 2026-11-30'. Audience and promotion are optional.*