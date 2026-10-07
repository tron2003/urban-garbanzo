from workflow_agent.agent import Agent
from workflow_agent.llm.base import LLMClient, LLMResponse


def by_kw(report):
    return {k["keyword"]: k for k in report.result.data["keywords"]}


def test_intent_classes(agent):
    k = by_kw(agent.run_workflow("WF008"))
    assert k["buy running shoes online"]["intent"] == "transactional"
    assert k["cheap yoga mat"]["intent"] == "transactional"
    assert k["best running shoes for flat feet"]["intent"] == "commercial"
    assert k["leather wallet vs fabric wallet"]["intent"] == "commercial"
    assert k["how to choose running shoes"]["intent"] == "informational"
    assert k["what is a tpe yoga mat"]["intent"] == "informational"
    assert k["nike running shoes official site"]["intent"] == "navigational"


def test_all_four_intents_are_produced(agent):
    counts = agent.run_workflow("WF008").result.data["intent_counts"]
    assert all(counts[i] > 0 for i in ("informational", "commercial", "transactional", "navigational"))


def test_duplicates_merged_with_max_volume(agent):
    r = agent.run_workflow("WF008")
    k = by_kw(r)
    assert "running  shoes" not in k and k["running shoes"]["volume"] == 12000    # 'Running Shoes' + 'running  shoes ' merged
    assert len(r.result.data["keywords"]) == 22                                     # 23 rows, 1 duplicate merged


def test_category_mapping_and_pages(agent):
    k = by_kw(agent.run_workflow("WF008"))
    assert k["buy running shoes online"]["category"] == "Footwear"
    assert k["buy running shoes online"]["target_page"] == "/collections/footwear"
    assert k["how to clean a leather wallet"]["target_page"].startswith("/blog/how-to-clean-a-leather-wallet")
    assert k["astrology compatibility"]["category"] == "Uncategorized"
    assert "review manually" in k["astrology compatibility"]["target_page"]


def test_priority_rules(agent):
    k = by_kw(agent.run_workflow("WF008"))
    assert k["running shoes"]["priority"] == "high"                  # 12000 x 0.8 = 9600
    assert k["buy running shoes online"]["priority"] == "high"       # 2400 x 1.0
    assert k["what is a tpe yoga mat"]["priority"] == "low"          # 260 x 0.4
    assert k["astrology compatibility"]["priority"] != "high"


def test_high_priority_come_first(agent):
    kws = agent.run_workflow("WF008").result.data["keywords"]
    order = [k["priority"] for k in kws]
    assert order == sorted(order, key={"high": 0, "medium": 1, "low": 2}.get)


def test_inline_keywords_without_volume(agent):
    r = agent.run_workflow("WF008", {"keywords": ["buy denim jacket", "how to wash denim", "denim jacket"]})
    assert r.status == "success" and len(r.result.data["keywords"]) == 3
    k = by_kw(r)
    assert k["buy denim jacket"]["priority"] == "high" and k["how to wash denim"]["priority"] == "low"


def test_inline_keywords_override_sample_file(agent):
    r = agent.run_workflow("WF008", {"keywords": ["buy yoga mat", "yoga mat tips"]})
    assert "keywords_file" not in r.params


def test_csv_artifact_written(agent, settings):
    r = agent.run_workflow("WF008")
    assert (settings.base_dir / r.result.artifacts[0]).exists()


def test_bad_file_and_empty_keywords(agent, tmp_path):
    assert agent.run_workflow("WF008", {"keywords_file": "nope.csv"}).status == "failed"
    f = tmp_path / "k.csv"; f.write_text("keyword,monthly_searches\n,\n  ,\n")
    r = agent.run_workflow("WF008", {"keywords_file": str(f)})
    assert r.status == "failed" and "no data rows" in r.error                 # header only
    g = tmp_path / "k2.csv"; g.write_text("keyword,monthly_searches\n ,100\n")
    assert agent.run_workflow("WF008", {"keywords_file": str(g)}).status == "needs_input"   # keyword cells blank


class IntentLLM(LLMClient):
    name, available = "intent", True
    def chat(self, messages, **kw):
        return LLMResponse(content='{"results": [{"keyword": "denim jacket", "intent": "commercial"}, {"keyword": "yoga mat", "intent": "transactional"}]}')


def test_llm_only_refines_low_confidence_keywords(settings):
    r = Agent(settings, llm=IntentLLM(), strict=False).run_workflow("WF008", {"keywords": ["buy yoga mat", "yoga mat", "denim jacket"]})
    k = by_kw(r)
    assert k["buy yoga mat"]["intent_source"] == "rules"
    assert k["yoga mat"]["intent_source"] == "llm" and k["yoga mat"]["intent"] == "transactional"
