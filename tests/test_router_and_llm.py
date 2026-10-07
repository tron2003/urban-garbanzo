import pytest

from workflow_agent.agent import Agent
from workflow_agent.core.errors import LLMUnavailable
from workflow_agent.llm import OfflineLLM
from workflow_agent.llm.base import OpenAICompatibleClient
from workflow_agent.router import WorkflowRouter, tool_name
from tests.conftest import make_settings
from tests.fake_llm_server import FakeLLM

# the ten requests from the workbook's Test_Questions sheet
SHEET = [("Which products need restocking?", "WF001"), ("Find products where vendor price differs by more than 10%.", "WF002"),
         ("Process this vendor spreadsheet and show invalid rows.", "WF003"), ("Generate SEO content for this product.", "WF004"),
         ("Where is order ORD-1001?", "WF005"), ("Find likely duplicate products in the catalog.", "WF006"),
         ("Create a campaign brief for the new collection.", "WF007"), ("Classify these keywords and map them to pages.", "WF008"),
         ("Assign this urgent task to the best available developer.", "WF009"), ("Which workflows are failing most often?", "WF010")]
PARAPHRASES = [("what items are running low on stock?", "WF001"), ("compare our prices against the supplier price list", "WF002"),
               ("clean up this supplier csv and tell me which rows are broken", "WF003"), ("I need an SEO title for a new product", "WF004"),
               ("track the package for ana.silva@example.com", "WF005"), ("are there any duplicate listings in the catalogue", "WF006"),
               ("draft a campaign brief to boost sales in November", "WF007"), ("group my SEO keywords by intent", "WF008"),
               ("allocate the checkout task to someone with react skills", "WF009"), ("which workflows are slow", "WF010")]


@pytest.fixture
def router(agent):
    return agent.router


@pytest.mark.parametrize("text,expected", SHEET + PARAPHRASES)
def test_heuristic_routing(router, text, expected):
    assert router.route_heuristic(text).workflow_id == expected


@pytest.mark.parametrize("text", ["what's the weather today", "tell me a joke", "hello", "convert 5 miles to km"])
def test_out_of_scope_is_not_forced_into_a_workflow(router, text):
    assert router.route_heuristic(text).workflow_id is None


def test_extractor_evidence_and_params(router):
    d = router.route("Where is order ord-1002?")
    assert d.workflow_id == "WF005" and d.params == {"order_id": "ORD-1002"}
    assert router.route("which items are below 15 in stock").params["threshold"] == 15.0


# ---------------- LLM tool-calling through the real HTTP client ----------------
@pytest.fixture
def server():
    made = []
    def make(replies):
        s = FakeLLM(replies); made.append(s); return s
    yield make
    for s in made:
        s.close()


def agent_for(server, tmp_path, **kw):
    llm = OpenAICompatibleClient(server.url, "sk-test", "test-model", timeout=5)
    return Agent(make_settings(tmp_path, **kw), llm=llm)


def test_llm_routes_via_tool_call_and_receives_excel_derived_tools(server, tmp_path):
    srv = server([{"tool": "wf005_customer_order_status", "args": {"order_id": "ORD-1003"}}])
    resp = agent_for(srv, tmp_path).handle("hey, can you check on 1003 for me")
    assert resp.route.method == "llm-tool-call" and resp.report.workflow_id == "WF005"
    assert resp.report.params["order_id"] == "ORD-1003"
    body = srv.requests[0]
    names = [t["function"]["name"] for t in body["tools"]]
    assert len(names) == 11 and "no_matching_workflow" in names and "wf001_inventory_restock_check" in names
    desc = next(t for t in body["tools"] if t["function"]["name"] == "wf007_marketing_campaign_brief")["function"]["description"]
    assert "User asks to create a campaign brief" in desc                    # straight from the Excel Trigger column
    assert body["tool_choice"] == "required" and body["model"] == "test-model"
    assert srv.headers[0]["Authorization"] == "Bearer sk-test"


def test_llm_args_are_validated_and_only_declared_params_survive(server, tmp_path):
    srv = server([{"tool": "wf001_inventory_restock_check", "args": {"threshold": "abc", "bogus": 1, "inventory_file": "data/inventory.csv"}}])
    r = agent_for(srv, tmp_path).handle("restock please")
    assert "threshold" not in r.report.params and "bogus" not in r.report.params
    assert r.report.param_sources["inventory_file"] == "user"


def test_llm_no_matching_workflow(server, tmp_path):
    srv = server([{"tool": "no_matching_workflow", "args": {"reason": "small talk"}}])
    r = agent_for(srv, tmp_path).handle("what a lovely day")
    assert r.kind == "no_match" and "small talk" in r.route.reason


@pytest.mark.parametrize("reply", [{"status": 500}, {"raw": "not json"}, {"content": "I think inventory"}, {"tool": "made_up_tool"}])
def test_llm_failures_fall_back_to_the_heuristic_router(server, tmp_path, reply):
    srv = server([reply])
    r = agent_for(srv, tmp_path).handle("Which products need restocking?")
    assert r.kind == "completed" and r.report.workflow_id == "WF001"
    assert r.route.method == "heuristic (LLM fallback)" and "LLM routing unavailable" in r.route.note


def test_llm_unreachable_endpoint(tmp_path):
    llm = OpenAICompatibleClient("http://127.0.0.1:9/v1", "", "m", timeout=1)
    with pytest.raises(LLMUnavailable) as e:
        llm.chat([{"role": "user", "content": "x"}])
    assert e.value.transient
    assert Agent(make_settings(tmp_path), llm=llm).handle("Which products need restocking?").kind == "completed"


def test_llm_json_text_reply_is_accepted(server, tmp_path):
    srv = server([{"content": 'Sure: {"workflow_id": "WF006", "reason": "duplicates"}'}])
    assert agent_for(srv, tmp_path).handle("dupes?").report.workflow_id == "WF006"


def test_end_to_end_generation_through_http_llm(server, tmp_path):
    srv = server([{"tool": "wf004_product_description_generator", "args": {}},
                  {"content": "A 30-liter pack with padded shoulder straps."}, {"content": "30L hiking pack in Forest Green"},
                  {"content": "TrailLite 30L Backpack | Outdoor Gear"}, {"content": "Discover the TrailLite 30L pack, in Forest Green."}])
    r = agent_for(srv, tmp_path).handle("Generate SEO content for this product.")
    assert r.report.result.data["generation_modes"] == {"description": "LLM", "short": "LLM", "seo_title": "LLM", "meta": "LLM"}
    assert "Material: [NOT PROVIDED]" in r.report.result.data["product_description"]
    assert len(srv.requests) == 5


def test_offline_llm_raises_and_client_factory(tmp_path):
    from workflow_agent.llm import build_llm
    s = make_settings(tmp_path)
    assert isinstance(build_llm(s), OfflineLLM)
    s.llm_provider, s.llm_api_key = "openai", "k"
    assert build_llm(s).model == "gpt-4o-mini"
    s.llm_provider, s.llm_model, s.llm_base_url = "openai_compatible", "llama3.1", "http://localhost:11434/v1"
    assert build_llm(s).base_url.endswith("/v1")
    s.llm_model = ""
    assert isinstance(build_llm(s), OfflineLLM)         # misconfigured -> safe offline mode
    with pytest.raises(LLMUnavailable):
        OfflineLLM().chat([])
