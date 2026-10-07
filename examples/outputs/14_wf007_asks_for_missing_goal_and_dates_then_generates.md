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

---

### Request

> Goal: increase autumn sales, from 2026-11-01 to 2026-11-30, promotion: 15% off for the first 48 hours, audience: young professionals

**Selected workflow:** `WF007` - Marketing Campaign Brief  
**Routing:** continued - your reply answers the question I asked  
**Parameters:** `campaign_goal=increase autumn sales`, `start_date=2026-11-01`, `end_date=2026-11-30`, `target_audience=young professionals`, `promotion=15% off for the first 48 hours`, `collection=new`, `products_file=data/products.csv` *(bundled sample)*

**Steps executed**

1. **success** - Validate inputs - Goal and dates present (30-day campaign)
2. **success** - identify campaign objective - Objective: Sales & conversion
3. **success** - summarize products - 5 product(s) selected (launch_status = new) across 3 categories
4. **success** - create messaging - Headline: 'Autumn 2026: made to be bought' via template (no LLM configured)
5. **success** - create channel recommendations - 6 channel(s) recommended for 'Sales & conversion'
6. **success** - create campaign checklist - 15 checklist items; brief saved to examples/outputs/artifacts/20261007-072101-f7f612/campaign_brief.md

**Conditions / decisions**

- goal and dates present: **yes** (2026-11-01 to 2026-11-30 (30 days))
- objective classification: **Sales & conversion** (from goal: 'increase autumn sales')
- channel mix: **6 channels** (driven by objective 'Sales & conversion' and audience)

**Tools / API calls**

- product_data_reader.select x1 (2 ms)

**Result (success)**

Campaign brief ready: Sales & conversion campaign for Autumn 2026, 2026-11-01 to 2026-11-30, 5 product(s), 6 channels, 15 checklist items.

_Objective & audience_

| Item | Detail |
|---|---|
| Objective | Sales & conversion - increase autumn sales |
| KPIs | revenue, conversion rate, average order value, ROAS |
| Audience | young professionals |
| Promotion | 15% off for the first 48 hours |
| Dates | 2026-11-01 to 2026-11-30 |
| Messaging by | template (no LLM configured) |

_Products_

| SKU | Name | Category | Price |
|---|---|---|---|
| SKU-1003 | Denim Jacket | Apparel | 79.00 |
| SKU-1005 | Canvas Tote Bag | Accessories | 12.50 |
| SKU-1006 | Running Shoes (42) | Footwear | 89.90 |
| SKU-1007 | Running Shoes (43) | Footwear | 89.90 |
| SKU-1008 | Wool Scarf | Accessories | 24.00 |

_Channel recommendations_

| Channel | Role | Why | KPI |
|---|---|---|---|
| Email & SMS | Primary | Highest-converting owned channel | conversion rate, revenue per send |
| Paid search & shopping ads | Primary | Captures high purchase intent | ROAS, CPA |
| Retargeting (paid social/display) | Secondary | Brings back cart/product viewers | ROAS, assisted conversions |
| Onsite banners & product badges | Secondary | Reinforces the offer at decision time | banner CTR, conversion |
| TikTok creators | Secondary | Audience skews young and short-video native | views, saves |
| Promo code on landing page + checkout | Supporting | Needed to redeem: 15% off for the first 48 hours | code redemption rate |

_Timeline_

| Phase | From | To | Focus |
|---|---|---|---|
| Preparation | 2026-10-18 | 2026-10-31 | Brief sign-off, creative, landing page, tracking, inventory check |
| Launch week | 2026-11-01 | 2026-11-07 | Go live, daily monitoring |
| Sustain & optimise | 2026-11-08 | 2026-11-23 | Weekly optimisation, creative refresh |
| Final push | 2026-11-24 | 2026-11-30 | Last-chance messaging |
| Wrap-up | 2026-12-01 | 2026-12-07 | Results, learnings, report |

_Checklist_

| Due |  | Task |
|---|---|---|
| 2026-10-18 |  | Confirm objective, KPIs and budget with stakeholders |
| 2026-10-22 |  | Approve creative assets and copy (headline, key messages, CTA) |
| 2026-10-25 |  | Build collection landing page; load product feed; configure promo '15% off for the first 48 hours' |
| 2026-10-27 |  | Check stock for featured SKUs (run the inventory restock check) |
| 2026-10-29 |  | Schedule emails, social posts and ad campaigns |
| 2026-10-31 |  | Final QA: links, UTM tracking, analytics goals |
| 2026-11-01 |  | GO LIVE - publish across all channels |
| 2026-11-02 |  | First-day performance check; fix any broken links |
| 2026-11-08 |  | Weekly performance review and optimisation |
| 2026-11-15 |  | Weekly performance review and optimisation |
| 2026-11-22 |  | Weekly performance review and optimisation |
| 2026-11-29 |  | Weekly performance review and optimisation |
| 2026-11-30 |  | Close campaign / end promotion |
| 2026-12-03 |  | Collect results from all channels |
| 2026-12-07 |  | Publish performance report vs KPIs and record learnings |

**Messaging**

```text
Headline: Autumn 2026: made to be bought
Tagline: Sales & conversion campaign, 01 Nov - 30 Nov 2026
- 5 products across Accessories, Apparel, Footwear.
- Built from Canvas, Denim, Merino wool, Mesh.
- Prices from 12.50 to 89.90.
- Offer: 15% off for the first 48 hours.
- Made for young professionals.
CTA: Shop now
```

Files written: `examples/outputs/artifacts/20261007-072101-f7f612/campaign_brief.md`