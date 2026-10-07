import json

import pytest

from workflow_agent.agent import Agent
from workflow_agent.llm.base import LLMClient, LLMResponse


FULL = {"product_name": "Aero Water Bottle", "category": "Drinkware", "attributes": ["750 ml", "leak-proof lid"],
        "material": "stainless steel", "color": "Silver", "target_audience": "gym-goers"}


def test_sample_product_marks_missing_not_invented(agent):
    report = agent.run_workflow("WF004")
    assert report.status == "success"
    d = report.result.data
    assert d["missing_attributes"] == ["material", "target_audience"]
    assert "Material: [NOT PROVIDED]" in d["product_description"]
    assert "Target audience: [NOT PROVIDED]" in d["product_description"]
    low = d["product_description"].lower()
    assert "cotton" not in low and "nylon" not in low
    assert any("Missing information" in w for w in report.warnings)


def test_length_limits_and_no_placeholders_in_seo_fields(agent):
    d = agent.run_workflow("WF004").result.data
    assert len(d["short_description"]) <= 160 and len(d["seo_title"]) <= 60 and len(d["meta_description"]) <= 155
    for key in ("short_description", "seo_title", "meta_description"):
        assert "[" not in d[key]


def test_complete_input_has_nothing_missing(agent):
    report = agent.run_workflow("WF004", FULL)
    assert report.result.data["missing_attributes"] == []
    assert "stainless steel" in report.result.data["product_description"]
    assert "[NOT PROVIDED]" not in report.result.data["product_description"]


def test_user_input_disables_sample(agent):
    # providing only a name must NOT silently borrow the sample's category/colour
    d = agent.run_workflow("WF004", {"product_name": "Mystery Gadget"}).result.data
    assert set(d["missing_attributes"]) == {"category", "attributes", "material", "color", "target_audience"}
    assert "Forest Green" not in d["product_description"]


def test_missing_product_name_asks_user(agent):
    agent.settings.allow_sample_defaults = False
    report = agent.run_workflow("WF004", {"material": "wood"})
    assert report.status == "needs_input" and report.clarification.missing == ["product_name"]


def test_long_name_title_is_trimmed(agent):
    name = "Ultra Premium Extra Long Named Hiking Backpack With Many Words In The Title"
    d = agent.run_workflow("WF004", {"product_name": name, "category": "Outdoor Gear"}).result.data
    assert len(d["seo_title"]) <= 60


class ScriptedLLM(LLMClient):
    name, available = "scripted", True

    def __init__(self, replies):
        self.replies, self.calls = list(replies), []

    def chat(self, messages, **kw):
        self.calls.append(messages)
        return LLMResponse(content=self.replies.pop(0) if self.replies else "Fine product text.")


def test_llm_output_with_invented_material_is_rejected_then_retried(settings):
    llm = ScriptedLLM(["A rugged cotton backpack for hikers.",          # invents cotton + hikers -> rejected
                       "A 30-liter pack with padded straps in Forest Green.",  # retry ok
                       "Compact 30L pack.", "TrailLite Backpack | Outdoor Gear", "Discover the TrailLite pack."])
    agent = Agent(settings, llm=llm, strict=False)
    report = agent.run_workflow("WF004")
    d = report.result.data
    assert "cotton" not in d["product_description"].lower()
    assert d["generation_modes"]["description"] == "LLM"
    assert len(llm.calls) == 5                       # 1 rejected + 1 retry + 3 other fields
    assert "rejected" in llm.calls[1][-1]["content"]


def test_llm_that_keeps_inventing_falls_back_to_template(settings):
    llm = ScriptedLLM(["Made of leather for men."] * 2 + ["ok short"] * 3)
    report = Agent(settings, llm=llm, strict=False).run_workflow("WF004")
    assert report.result.data["generation_modes"]["description"].startswith("template")
    assert any("rejected" in w for w in report.warnings)


def test_llm_outage_falls_back_without_failing(settings):
    from workflow_agent.core.errors import LLMUnavailable

    class Down(LLMClient):
        name, available = "down", True
        def chat(self, *a, **k):
            raise LLMUnavailable("endpoint unreachable", transient=True)

    report = Agent(settings, llm=Down(), strict=False).run_workflow("WF004")
    assert report.status == "success"
    assert all(m.startswith("template") for m in report.result.data["generation_modes"].values())
    assert any(c.status == "error" for c in report.tool_calls)
