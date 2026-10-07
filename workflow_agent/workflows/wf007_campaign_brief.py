"""WF007 - Marketing Campaign Brief.

Rule (from Excel): if campaign goal or dates are missing, request them BEFORE generating the brief.
So 'Create a campaign brief for the new collection.' (no goal, no dates) deliberately stops at step 1 and asks.
Optional inputs (audience, promotion) are never invented: the brief lists them under Assumptions.
"""
from __future__ import annotations

import re
from datetime import timedelta

from ..core.errors import NeedMoreInput, StepError, ToolError
from ..core.models import Param, Table
from ..core.registry import WorkflowModule
from ..utils import find_dates
from .common import file_extractor, kv_extractor

GOAL_STOP = r"(?=\s*(?:[;.\n]|\bfrom\b|\bbetween\b|\bstarting\b|\brunning\b|\bduring\b|\bfor the\b|,\s*(?:audience|target|promotion|promo|dates?)\b|$))"
_GOAL_RX = [
    re.compile(r"\b(?:goal|objective|aim)\s*(?:is|:|=)\s*(?:to\s+)?(.+?)" + GOAL_STOP, re.I),
    re.compile(r"\bto\s+((?:increase|boost|drive|grow|raise|promote|launch|build|generate|improve|maximi[sz]e|reach|"
               r"attract|acquire|retain|create|raise)\b.+?)" + GOAL_STOP, re.I),
]


def _goal(text: str):
    for rx in _GOAL_RX:
        m = rx.search(text or "")
        if m:
            return m.group(1).strip(" ,")
    return None


def _date_at(i: int):
    def extract(text: str):
        ds = find_dates(text or "")
        return ds[i].isoformat() if len(ds) > i else None
    return extract


def _collection(text: str):
    m = re.search(r"\bcollection\s*[:=]\s*([\w .&-]+?)(?=\s*(?:[;.\n,]|$))", text or "", re.I)
    if m:
        return m.group(1).strip()
    m = re.search(r"\b(?:for|of|on)\s+the\s+([\w .&-]+?)\s+(?:collection|range|line)\b", text or "", re.I)
    return m.group(1).strip() if m else None


def _skus(text: str):
    found = re.findall(r"\bSKU-\d+\b", text or "", re.I)
    return [f.upper() for f in found] or None


def _promotion(text: str):
    kv = kv_extractor(["promotion", "promo", "offer"], ["goal", "objective", "audience", "target audience", "dates"])(text)
    if kv:
        return kv
    m = re.search(r"(\d{1,2}\s*%\s*off[^.;,\n]*|buy one,? get one[^.;,\n]*|free shipping[^.;,\n]*)", text or "", re.I)
    return m.group(1).strip() if m else None


wf = WorkflowModule(
    "WF007",
    params=[
        Param("campaign_goal", "The campaign goal / objective in the user's words", required=True, extractor=_goal),
        Param("start_date", "Campaign start date (YYYY-MM-DD)", required=True, extractor=_date_at(0)),
        Param("end_date", "Campaign end date (YYYY-MM-DD)", required=True, extractor=_date_at(1)),
        Param("target_audience", "Target audience (optional)",
              extractor=kv_extractor(["target audience", "audience", "targeting", "aimed at"],
                                     ["goal", "objective", "promotion", "promo", "dates", "collection"])),
        Param("promotion", "Promotion or offer (optional)", extractor=_promotion),
        Param("collection", "Collection name, or 'new' for products flagged as new", extractor=_collection),
        Param("skus", "Specific product SKUs to feature", type="array", extractor=_skus),
        Param("products_file", "Product catalogue CSV", type="file", sample_default="data/products.csv",
              extractor=file_extractor("csv")),
    ],
    routing_hints=["campaign brief", "marketing campaign", "campaign plan", "promotion plan", "launch campaign",
                   "marketing brief", "create a campaign", "promote the collection"],
)

OBJECTIVES = [   # (key, label, keywords, primary KPIs)
    ("launch", "Product launch", ["launch", "introduce", "unveil", "new collection", "debut", "new arrivals"],
     "launch-week units sold, new-customer share, collection page views"),
    ("sales", "Sales & conversion", ["sales", "revenue", "convert", "conversion", "purchase", "sell", "orders", "boost sales"],
     "revenue, conversion rate, average order value, ROAS"),
    ("awareness", "Brand awareness", ["awareness", "brand", "reach", "visibility", "exposure", "impressions"],
     "reach, impressions, social engagement, branded search volume"),
    ("retention", "Customer retention", ["retain", "retention", "loyalty", "repeat", "returning", "reactivate"],
     "repeat purchase rate, email click-through, loyalty sign-ups"),
    ("engagement", "Engagement & lead generation", ["engage", "engagement", "traffic", "subscribers", "followers", "leads", "sign-ups", "signups"],
     "sessions, subscriber growth, engagement rate"),
    ("sellthrough", "Inventory sell-through", ["clear", "clearance", "sell-through", "sell through", "surplus", "overstock"],
     "sell-through %, units cleared, margin after discount"),
]

CHANNELS = {   # key -> [(channel, role, why, KPI)]
    "launch": [("Instagram & TikTok (organic + paid)", "Primary", "Visual launch storytelling for new product", "reach, saves, click-through"),
               ("Email to existing customers", "Primary", "Fastest route to warm buyers on launch day", "open rate, click-through, launch-day revenue"),
               ("Influencer / UGC seeding", "Secondary", "Social proof for a collection with no reviews yet", "engagement, referred sessions"),
               ("Onsite hero banner + collection page", "Secondary", "Converts visitors already on site", "collection page conversion")],
    "sales": [("Email & SMS", "Primary", "Highest-converting owned channel", "conversion rate, revenue per send"),
              ("Paid search & shopping ads", "Primary", "Captures high purchase intent", "ROAS, CPA"),
              ("Retargeting (paid social/display)", "Secondary", "Brings back cart/product viewers", "ROAS, assisted conversions"),
              ("Onsite banners & product badges", "Secondary", "Reinforces the offer at decision time", "banner CTR, conversion")],
    "awareness": [("Paid social (video-first)", "Primary", "Scalable reach with creative testing", "reach, CPM, video views"),
                  ("Influencer partnerships", "Primary", "Borrowed trust and audience", "reach, engagement"),
                  ("PR / press outreach", "Secondary", "Earned coverage and backlinks", "mentions, referral traffic"),
                  ("Organic social & SEO content", "Secondary", "Compounding brand discovery", "branded search, followers")],
    "retention": [("Email / CRM journeys", "Primary", "Owned, personalised, low cost", "repeat purchase rate"),
                  ("SMS / push notifications", "Secondary", "Timely nudges to lapsed customers", "reactivation rate"),
                  ("Loyalty programme messaging", "Secondary", "Rewards repeat behaviour", "loyalty sign-ups")],
    "engagement": [("Organic social content", "Primary", "Builds community and followers", "engagement rate"),
                   ("Email newsletter", "Secondary", "Drives repeat visits and sign-ups", "click-through"),
                   ("Blog / SEO content", "Secondary", "Long-term organic traffic", "organic sessions")],
    "sellthrough": [("Email & SMS flash offers", "Primary", "Fast, cheap reach to buyers", "units sold per send"),
                    ("Onsite banners & clearance page", "Primary", "Concentrates demand on target SKUs", "clearance page conversion"),
                    ("Retargeting ads", "Secondary", "Recovers viewers who did not buy", "ROAS")],
    "general": [("Email", "Primary", "Owned channel to announce the promotion", "click-through"),
                ("Paid social", "Secondary", "Broadens reach", "CTR, CPA"),
                ("Onsite banners", "Secondary", "Highlights the offer to visitors", "banner CTR")],
}

SYSTEM = ("You are a marketing strategist. Use ONLY the facts provided. Do not invent discounts, prices, dates, product "
          "features, materials or claims that are not in the facts. Reply with JSON only.")


def _fmt_list(items, limit=3):
    items = [i for i in items if i]
    return ", ".join(items[:limit]) + (f" +{len(items) - limit} more" if len(items) > limit else "")


@wf.step("Validate inputs")
def validate(ctx):
    missing = []
    goal = (ctx.param("campaign_goal") or "").strip()
    if not goal:
        missing.append("campaign goal")
    start, end = ctx.param("start_date"), ctx.param("end_date")
    ds, de = (find_dates(str(start), ctx.today) if start else []), (find_dates(str(end), ctx.today) if end else [])
    if not ds or not de:
        missing.append("campaign dates (start and end)")
    if missing:
        ctx.decide("goal and dates present", "no - asking before generating", "Excel rule: request missing goal/dates first")
        raise NeedMoreInput(
            "Before I write the brief I need: " + " and ".join(missing) + ". "
            "For example: 'Goal: increase autumn sales, from 2026-11-01 to 2026-11-30'. "
            "Audience and promotion are optional.", ["campaign_goal" if not goal else "dates"] if len(missing) == 1 else ["campaign_goal", "dates"])
    start_d, end_d = ds[0], de[0]
    if end_d < start_d:
        raise NeedMoreInput(f"The end date ({end_d.isoformat()}) is before the start date ({start_d.isoformat()}). "
                            "Please give me corrected campaign dates.", ["dates"])
    ctx.state.update(goal=goal, start=start_d, end=end_d, days=(end_d - start_d).days + 1)
    ctx.decide("goal and dates present", "yes", f"{start_d.isoformat()} to {end_d.isoformat()} ({ctx.state['days']} days)")
    if start_d < ctx.today:
        ctx.warn(f"The start date {start_d.isoformat()} is in the past; checklist dates before today are marked 'past'.")
    return f"Goal and dates present ({ctx.state['days']}-day campaign)"


@wf.step("identify campaign objective")
def objective(ctx):
    text = ctx.state["goal"].lower()
    hits = [(k, label, kpi) for k, label, words, kpi in OBJECTIVES if any(w in text for w in words)]
    if hits:
        key, label, kpi = hits[0]
        secondary = [h[1] for h in hits[1:]]
    else:
        key, label, kpi, secondary = "general", "General promotion", "clicks, conversions, revenue", []
        ctx.warn("The goal did not match a known objective type; treated as a general promotion.")
    ctx.state.update(obj_key=key, obj_label=label, kpi=kpi, secondary=secondary)
    ctx.decide("objective classification", label, f"from goal: '{ctx.state['goal']}'")
    return f"Objective: {label}" + (f" (secondary: {', '.join(secondary)})" if secondary else "")


@wf.step("summarize products")
def products(ctx):
    skus, collection = ctx.param("skus"), ctx.param("collection")
    try:
        res = ctx.call_tool("product_data_reader", op="select", path=str(ctx.param("products_file")),
                            skus=skus, collection=collection)
    except ToolError as exc:
        raise StepError(f"Could not read the product data: {exc.message}",
                        hint="Pass products_file=<csv> or check the file path.") from exc
    prods = res["products"]
    if not prods:
        raise StepError(f"No products matched ({res['selection']}).",
                        hint="Available collections: " + (", ".join(res["collections"]) or "none") + ". Use 'new' for new arrivals.")
    if not skus and not collection:
        ctx.warn("No collection or SKUs were specified, so every product in the catalogue is featured.")
    prices = [float(p["price"]) for p in prods if re.fullmatch(r"\d+(\.\d+)?", p.get("price", "") or "") and float(p["price"]) > 0]
    cats = sorted({p.get("category", "") for p in prods if p.get("category")})
    materials = sorted({p.get("material", "") for p in prods if p.get("material")})
    audiences = sorted({p.get("target_audience", "") for p in prods if p.get("target_audience")})
    label = collection if collection and collection.lower() not in {"new", "latest", "upcoming"} else (
        prods[0].get("collection") if len({p.get("collection") for p in prods}) == 1 else "the featured products")
    ctx.state.update(prods=prods, cats=cats, materials=materials, audiences_in_data=audiences,
                     price_min=min(prices) if prices else None, price_max=max(prices) if prices else None,
                     collection_label=label or "the featured products", selection=res["selection"])
    return f"{len(prods)} product(s) selected ({res['selection']}) across {len(cats)} categor{'y' if len(cats) == 1 else 'ies'}"


def _template_messaging(ctx) -> dict:
    s = ctx.state
    promo, aud = ctx.param("promotion"), ctx.param("target_audience")
    label = s["collection_label"]
    heads = {"launch": f"Meet {label}", "sales": f"{label}: made to be bought", "awareness": f"Discover {label}",
             "retention": f"A thank-you for our regulars: {label}", "engagement": f"Join the conversation: {label}",
             "sellthrough": f"Last chance on {label}", "general": f"Introducing {label}"}
    msgs = [f"{len(s['prods'])} products across {_fmt_list(s['cats'], 4)}."]
    if s["materials"]:
        msgs.append(f"Built from {_fmt_list(s['materials'], 4)}.")
    if s["price_min"] is not None:
        msgs.append(f"Prices from {s['price_min']:.2f} to {s['price_max']:.2f}." if s["price_max"] != s["price_min"] else f"Priced at {s['price_min']:.2f}.")
    if promo:
        msgs.append(f"Offer: {promo}.")
    if aud:
        msgs.append(f"Made for {aud}.")
    ctas = {"launch": "Shop the new collection", "sales": "Shop now", "awareness": "Discover more",
            "retention": "Claim your reward", "engagement": "Join in", "sellthrough": "Grab yours before it's gone", "general": "Shop now"}
    return {"headline": heads[s["obj_key"]], "tagline": f"{s['obj_label']} campaign, {s['start'].strftime('%d %b')} - {s['end'].strftime('%d %b %Y')}",
            "key_messages": msgs, "call_to_action": ctas[s["obj_key"]]}


@wf.step("create messaging")
def messaging(ctx):
    s = ctx.state
    template = _template_messaging(ctx)
    s["messaging_mode"], msg = "template (no LLM configured)", template
    if ctx.llm_available:
        facts = (f"Objective: {s['obj_label']} (goal: {s['goal']})\nDates: {s['start']} to {s['end']}\n"
                 f"Audience: {ctx.param('target_audience') or 'NOT SPECIFIED'}\nPromotion: {ctx.param('promotion') or 'NONE'}\n"
                 f"Collection: {s['collection_label']}\nProducts: " +
                 "; ".join(f"{p['name']} ({p.get('category', '')}, {p.get('material', '')}, {p.get('color', '')}, {p.get('price', '')})" for p in s["prods"][:15]))
        prompt = (facts + '\n\nReturn JSON: {"headline": str, "tagline": str, "key_messages": [3-5 str], "call_to_action": str}')
        try:
            raw = ctx.call_tool("llm", op="json", system=SYSTEM, prompt=prompt, max_tokens=500)
            ok = (isinstance(raw, dict) and isinstance(raw.get("headline"), str) and isinstance(raw.get("tagline"), str)
                  and isinstance(raw.get("call_to_action"), str) and isinstance(raw.get("key_messages"), list)
                  and 2 <= len(raw["key_messages"]) <= 6 and all(isinstance(m, str) for m in raw["key_messages"]))
            if not ok:
                raise ToolError("llm", "JSON did not match the expected shape")
            blob = " ".join([raw["headline"], raw["tagline"], raw["call_to_action"], *raw["key_messages"]])
            if not ctx.param("promotion") and re.search(r"\d+\s*%|\bdiscount|\bsale\b|free shipping|\bcoupon", blob, re.I):
                raise ToolError("llm", "invented a promotion that was not supplied")
            msg, s["messaging_mode"] = raw, "LLM"
        except ToolError as exc:
            ctx.warn(f"LLM messaging unavailable or rejected ({exc.message}); used deterministic template")
            s["messaging_mode"] = "template (LLM output rejected or unavailable)"
    s["messaging"] = msg
    return f"Headline: '{msg['headline']}' via {s['messaging_mode']}"


@wf.step("create channel recommendations")
def channels(ctx):
    s = ctx.state
    rows = list(CHANNELS.get(s["obj_key"], CHANNELS["general"]))
    aud = (ctx.param("target_audience") or "").lower()
    if re.search(r"\b(young|gen z|student|teen|college)\b", aud) and not any("TikTok" in r[0] for r in rows):
        rows.append(("TikTok creators", "Secondary", "Audience skews young and short-video native", "views, saves"))
    if re.search(r"\b(professional|b2b|business|commuter|remote)\b", aud):
        rows.append(("LinkedIn / professional email", "Secondary", "Audience is work-focused", "click-through"))
    if ctx.param("promotion"):
        rows.append(("Promo code on landing page + checkout", "Supporting", f"Needed to redeem: {ctx.param('promotion')}", "code redemption rate"))
    s["channels"] = rows
    ctx.decide("channel mix", f"{len(rows)} channels", f"driven by objective '{s['obj_label']}'" + (" and audience" if aud else ""))
    return f"{len(rows)} channel(s) recommended for '{s['obj_label']}'"


def _timeline(start, end):
    dur = (end - start).days + 1
    d = lambda n: start + timedelta(days=n)
    phases = [("Preparation", start - timedelta(days=14), start - timedelta(days=1), "Brief sign-off, creative, landing page, tracking, inventory check")]
    if dur <= 7:
        phases.append(("Launch & run", start, end, "Go live, monitor daily"))
    elif dur <= 21:
        phases += [("Launch", start, d(2), "Go live across all channels"),
                   ("Run & optimise", d(3), end - timedelta(days=3), "Monitor, rotate creative, adjust spend"),
                   ("Final push", end - timedelta(days=2), end, "Last-chance messaging")]
    else:
        phases += [("Launch week", start, d(6), "Go live, daily monitoring"),
                   ("Sustain & optimise", d(7), end - timedelta(days=7), "Weekly optimisation, creative refresh"),
                   ("Final push", end - timedelta(days=6), end, "Last-chance messaging")]
    phases.append(("Wrap-up", end + timedelta(days=1), end + timedelta(days=7), "Results, learnings, report"))
    return phases


@wf.step("create campaign checklist")
def checklist(ctx):
    s = ctx.state
    start, end, today = s["start"], s["end"], ctx.today
    T = lambda n: start + timedelta(days=n)
    items = [(T(-14), "Confirm objective, KPIs and budget with stakeholders"),
             (T(-10), "Approve creative assets and copy (headline, key messages, CTA)"),
             (T(-7), "Build collection landing page; load product feed" + (f"; configure promo '{ctx.param('promotion')}'" if ctx.param("promotion") else "")),
             (T(-5), "Check stock for featured SKUs (run the inventory restock check)"),
             (T(-3), "Schedule emails, social posts and ad campaigns"),
             (T(-1), "Final QA: links, UTM tracking, analytics goals"),
             (start, "GO LIVE - publish across all channels"),
             (T(1), "First-day performance check; fix any broken links")]
    t = start + timedelta(days=7)
    while t < end:
        items.append((t, "Weekly performance review and optimisation")); t += timedelta(days=7)
    items += [(end, "Close campaign / end promotion"), (end + timedelta(days=3), "Collect results from all channels"),
              (end + timedelta(days=7), "Publish performance report vs KPIs and record learnings")]
    items.sort(key=lambda x: x[0])
    rows = [[d.isoformat(), "past" if d < today else "", task] for d, task in items]
    past_prep = sum(1 for d, _ in items if d < today and d < start)
    if past_prep:
        ctx.warn(f"{past_prep} preparation task(s) fall before today ({today.isoformat()}): the prep window is shorter than the recommended 14 days.")

    phases = _timeline(start, end)
    aud = ctx.param("target_audience")
    assumptions = []
    if not aud:
        assumptions.append("Target audience not specified." + (f" Catalogue data suggests: {_fmt_list(s['audiences_in_data'], 5)}." if s["audiences_in_data"] else ""))
    if not ctx.param("promotion"):
        assumptions.append("No promotion specified - messaging contains no offer or discount.")
    if not ctx.param("skus") and not ctx.param("collection"):
        assumptions.append("No collection/SKUs specified - all catalogue products are featured.")
    m = s["messaging"]
    md = [f"# Campaign brief: {s['collection_label']}", "",
          f"**Objective:** {s['obj_label']} - {s['goal']}", f"**Dates:** {start.isoformat()} to {end.isoformat()} ({s['days']} days)",
          f"**Audience:** {aud or 'not specified'}", f"**Promotion:** {ctx.param('promotion') or 'none'}", f"**KPIs:** {s['kpi']}", "",
          "## Products", *[f"- {p['sku']} {p['name']} ({p.get('category', '')}, {p.get('price', '')})" for p in s["prods"]], "",
          "## Messaging", f"**Headline:** {m['headline']}", f"**Tagline:** {m['tagline']}", *[f"- {x}" for x in m["key_messages"]],
          f"**CTA:** {m['call_to_action']}", "", "## Channels", *[f"- **{c[0]}** ({c[1]}): {c[2]}. KPI: {c[3]}" for c in s["channels"]], "",
          "## Timeline", *[f"- **{n}** {a.isoformat()} to {b.isoformat()}: {desc}" for n, a, b, desc in phases], "",
          "## Checklist", *[f"- [ ] {r[0]} - {r[2]}" for r in rows]]
    if assumptions:
        md += ["", "## Assumptions", *[f"- {a}" for a in assumptions]]
    brief_md = "\n".join(md)
    artifact = ctx.write_text_artifact("campaign_brief.md", brief_md)

    ctx.set_result(
        f"Campaign brief ready: {s['obj_label']} campaign for {s['collection_label']}, {start.isoformat()} to {end.isoformat()}, "
        f"{len(s['prods'])} product(s), {len(s['channels'])} channels, {len(rows)} checklist items.",
        tables=[Table("Objective & audience", ["Item", "Detail"], [
                    ["Objective", f"{s['obj_label']} - {s['goal']}"], ["KPIs", s["kpi"]],
                    ["Audience", aud or "not specified"], ["Promotion", ctx.param("promotion") or "none"],
                    ["Dates", f"{start.isoformat()} to {end.isoformat()}"], ["Messaging by", s["messaging_mode"]]]),
                Table("Products", ["SKU", "Name", "Category", "Price"], [[p["sku"], p["name"], p.get("category", ""), p.get("price", "")] for p in s["prods"]]),
                Table("Channel recommendations", ["Channel", "Role", "Why", "KPI"], [list(c) for c in s["channels"]]),
                Table("Timeline", ["Phase", "From", "To", "Focus"], [[n, a.isoformat(), b.isoformat(), d] for n, a, b, d in phases]),
                Table("Checklist", ["Due", "", "Task"], rows)],
        text_blocks=[("Messaging", f"Headline: {m['headline']}\nTagline: {m['tagline']}\n" + "\n".join(f"- {x}" for x in m["key_messages"]) + f"\nCTA: {m['call_to_action']}")]
                    + ([("Assumptions", "\n".join(f"- {a}" for a in assumptions))] if assumptions else []),
        data={"objective": s["obj_label"], "goal": s["goal"], "start": start.isoformat(), "end": end.isoformat(),
              "products": [p["sku"] for p in s["prods"]], "messaging": m, "channels": [c[0] for c in s["channels"]],
              "timeline": [n for n, *_ in phases], "checklist_items": len(rows), "assumptions": assumptions},
        artifacts=[artifact])
    return f"{len(rows)} checklist items; brief saved to {artifact}"
