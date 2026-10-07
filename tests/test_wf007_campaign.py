from workflow_agent.agent import Agent
from workflow_agent.llm.base import LLMClient, LLMResponse

FULL = {"campaign_goal": "increase autumn sales", "start_date": "2026-11-01", "end_date": "2026-11-30",
        "collection": "new", "promotion": "15% off for 48 hours", "target_audience": "young professionals"}


def test_missing_goal_and_dates_asks_before_generating(agent):
    r = agent.run_workflow("WF007", {"collection": "new"})       # the Excel test request, minus details
    assert r.status == "needs_input"
    assert "campaign goal" in r.clarification.message and "dates" in r.clarification.message
    assert r.steps[0].status == "needs_input" and all(s.status == "skipped" for s in r.steps[1:])
    assert r.result is None and not r.tool_calls                  # nothing was generated or read


def test_only_dates_missing(agent):
    r = agent.run_workflow("WF007", {"campaign_goal": "boost sales"})
    assert r.status == "needs_input" and "dates" in r.clarification.message and "goal" not in r.clarification.message.split("need:")[1].split(".")[0]


def test_end_before_start_asks_again(agent):
    r = agent.run_workflow("WF007", FULL | {"start_date": "2026-12-01", "end_date": "2026-11-01"})
    assert r.status == "needs_input" and "before the start" in r.clarification.message


def test_full_brief_structure(agent):
    r = agent.run_workflow("WF007", FULL)
    assert r.status == "success"
    d = r.result.data
    assert d["objective"] == "Sales & conversion"
    assert d["products"] == ["SKU-1003", "SKU-1005", "SKU-1006", "SKU-1007", "SKU-1008"]     # launch_status = new
    assert d["timeline"] == ["Preparation", "Launch week", "Sustain & optimise", "Final push", "Wrap-up"]
    titles = [t.title for t in r.result.tables]
    assert {"Channel recommendations", "Timeline", "Checklist", "Products"} <= set(titles)
    assert any("Promo code" in c for c in d["channels"])
    assert r.result.artifacts and r.result.artifacts[0].endswith("campaign_brief.md")


def test_no_invented_promotion_in_template(agent):
    d = agent.run_workflow("WF007", FULL | {"promotion": None}).result.data
    text = " ".join([d["messaging"]["headline"], *d["messaging"]["key_messages"]]).lower()
    assert "%" not in text and "discount" not in text
    assert any("No promotion" in a for a in d["assumptions"])


def test_collection_by_name_and_unknown_collection(agent):
    ok = agent.run_workflow("WF007", FULL | {"collection": "Core Basics"})
    assert len(ok.result.data["products"]) == 7
    bad = agent.run_workflow("WF007", FULL | {"collection": "Spring 1999"})
    assert bad.status == "failed" and "Autumn 2026" in bad.error_hint


def test_short_campaign_uses_compact_timeline(agent):
    d = agent.run_workflow("WF007", FULL | {"start_date": "2026-11-01", "end_date": "2026-11-05"}).result.data
    assert d["timeline"] == ["Preparation", "Launch & run", "Wrap-up"]


def test_past_start_date_warns(agent):
    r = agent.run_workflow("WF007", FULL | {"start_date": "2026-10-01", "end_date": "2026-10-20"})
    assert any("in the past" in w for w in r.warnings)


class Scripted(LLMClient):
    name, available = "scripted", True
    def __init__(self, payload): self.payload = payload
    def chat(self, messages, **kw): return LLMResponse(content=self.payload)


def test_llm_messaging_used_when_valid(settings):
    good = '{"headline": "Autumn, ready", "tagline": "New pieces", "key_messages": ["Denim and wool", "Five new products"], "call_to_action": "Shop"}'
    r = Agent(settings, llm=Scripted(good), strict=False).run_workflow("WF007", FULL)
    assert r.result.data["messaging"]["headline"] == "Autumn, ready"


def test_llm_inventing_a_discount_is_rejected(settings):
    bad = '{"headline": "Autumn", "tagline": "t", "key_messages": ["Save 30% today", "x"], "call_to_action": "Shop"}'
    r = Agent(settings, llm=Scripted(bad), strict=False).run_workflow("WF007", FULL | {"promotion": None})
    assert "30%" not in str(r.result.data["messaging"])
    assert any("invented a promotion" in w for w in r.warnings)


def test_llm_garbage_json_falls_back(settings):
    r = Agent(settings, llm=Scripted("not json at all"), strict=False).run_workflow("WF007", FULL)
    assert r.status == "success" and any("deterministic template" in w for w in r.warnings)
