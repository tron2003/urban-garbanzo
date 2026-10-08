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


# ---------------- providers: openrouter, vllm, key hygiene ----------------
def test_openrouter_defaults_and_headers(tmp_path, monkeypatch):
    from workflow_agent.llm import build_llm
    monkeypatch.setenv("OPENROUTER_REFERER", "https://example.com")
    s = make_settings(tmp_path, llm_provider="openrouter", llm_api_key="sk-or-1")
    c = build_llm(s)
    assert c.base_url == "https://openrouter.ai/api/v1" and c.model == "openai/gpt-4o-mini"
    assert c.extra_headers["X-Title"] == "workflow-agent" and c.extra_headers["HTTP-Referer"] == "https://example.com"
    s.llm_model = "meta-llama/llama-3.1-70b-instruct"
    assert build_llm(s).model == "meta-llama/llama-3.1-70b-instruct"
    s.llm_api_key = ""
    assert isinstance(build_llm(s), OfflineLLM)               # key is required for hosted providers


def test_openrouter_sends_bearer_and_attribution_headers_over_http(server, tmp_path):
    srv = server([{"tool": "wf006_duplicate_product_detection", "args": {}}])
    llm = OpenAICompatibleClient(srv.url, "sk-or-9", "openai/gpt-4o-mini", 5, "openrouter", {"X-Title": "workflow-agent"})
    assert Agent(make_settings(tmp_path), llm=llm).handle("dupes?").report.workflow_id == "WF006"
    assert srv.headers[0]["Authorization"] == "Bearer sk-or-9" and srv.headers[0]["X-Title"] == "workflow-agent"
    assert srv.requests[0]["model"] == "openai/gpt-4o-mini"


def test_vllm_discovers_the_served_model_and_routes(server, tmp_path):
    from workflow_agent.llm import build_llm
    srv = server([{"tool": "wf001_inventory_restock_check", "args": {}}], ) 
    srv.models = ["Qwen/Qwen2.5-7B-Instruct"]
    s = make_settings(tmp_path, llm_provider="vllm", llm_base_url=srv.url)
    llm = build_llm(s)
    assert llm.model == "Qwen/Qwen2.5-7B-Instruct" and llm.name == "vllm:Qwen/Qwen2.5-7B-Instruct"
    r = Agent(s, llm=llm).handle("what needs reordering")
    assert r.route.method == "llm-tool-call" and r.report.workflow_id == "WF001"
    assert srv.requests[0]["model"] == "Qwen/Qwen2.5-7B-Instruct" and "Authorization" not in srv.headers[0]   # no key -> no header


def test_vllm_explicit_model_and_unreachable_server_is_offline(tmp_path):
    from workflow_agent.llm import build_llm
    s = make_settings(tmp_path, llm_provider="vllm", llm_model="my-model")
    assert build_llm(s).base_url == "http://localhost:8000/v1" and build_llm(s).model == "my-model"
    s2 = make_settings(tmp_path, llm_provider="vllm", llm_base_url="http://127.0.0.1:9/v1")
    assert isinstance(build_llm(s2), OfflineLLM)               # nothing to discover -> safe offline mode


def test_api_keys_are_never_sent_to_the_wrong_provider(monkeypatch, tmp_path):
    from workflow_agent.config import Settings
    for k in ("LLM_PROVIDER", "LLM_API_KEY", "LLM_BASE_URL", "OPENAI_API_KEY", "OPENROUTER_API_KEY", "VLLM_API_KEY"):
        monkeypatch.delenv(k, raising=False)
    monkeypatch.setenv("OPENAI_API_KEY", "sk-openai")
    monkeypatch.setenv("LLM_PROVIDER", "openrouter")
    assert Settings.from_env(tmp_path).llm_api_key == ""                      # OpenAI key NOT reused for OpenRouter
    monkeypatch.setenv("OPENROUTER_API_KEY", "sk-or")
    assert Settings.from_env(tmp_path).llm_api_key == "sk-or"
    monkeypatch.setenv("LLM_PROVIDER", "vllm")
    assert Settings.from_env(tmp_path).llm_api_key == ""
    monkeypatch.setenv("LLM_API_KEY", "generic")
    assert Settings.from_env(tmp_path).llm_api_key == "generic"


def test_provider_auto_detection(monkeypatch, tmp_path):
    from workflow_agent.config import Settings
    for k in ("LLM_PROVIDER", "LLM_API_KEY", "LLM_BASE_URL", "OPENAI_API_KEY", "OPENROUTER_API_KEY", "VLLM_API_KEY"):
        monkeypatch.delenv(k, raising=False)
    assert Settings.from_env(tmp_path).llm_provider == "none"
    monkeypatch.setenv("OPENROUTER_API_KEY", "k")
    assert Settings.from_env(tmp_path).llm_provider == "openrouter"
    monkeypatch.setenv("OPENAI_API_KEY", "k")
    assert Settings.from_env(tmp_path).llm_provider == "openai"
    monkeypatch.setenv("LLM_BASE_URL", "http://x/v1")
    assert Settings.from_env(tmp_path).llm_provider == "openai_compatible"


# ---------------- regression: found by a live OpenRouter run ----------------
def test_model_refusing_because_an_input_is_missing_is_overridden_by_a_strong_match(server, tmp_path):
    """A real model answered 'no_matching_workflow: I need the inventory file path'. Missing inputs are not a reason to refuse."""
    srv = server([{"tool": "no_matching_workflow", "args": {"reason": "I need the inventory CSV file path first"}}])
    r = agent_for(srv, tmp_path).handle("Which products need restocking?")
    assert r.kind == "completed" and r.report.workflow_id == "WF001"
    assert r.route.method == "heuristic (LLM said no match)" and "inventory CSV file path" in r.route.note


def test_genuinely_unrelated_requests_stay_unmatched_even_with_the_override(server, tmp_path):
    srv = server([{"tool": "no_matching_workflow", "args": {"reason": "weather question"}}])
    assert agent_for(srv, tmp_path).handle("what's the weather like in Paris").kind == "no_match"


def test_router_prompt_tells_the_model_that_missing_inputs_are_fine(server, tmp_path):
    srv = server([{"tool": "wf001_inventory_restock_check", "args": {}}])
    agent_for(srv, tmp_path).handle("Which products need restocking?")
    system = srv.requests[0]["messages"][0]["content"]
    assert "NEVER a reason to refuse" in system and "ONLY when the request is unrelated" in system


# ---------------- regression: reasoning models (found with apodex/apodex-1.1-mini:free) ----------------
def test_openrouter_disables_reasoning_by_default_and_other_providers_are_untouched(tmp_path):
    from workflow_agent.llm import build_llm
    s = make_settings(tmp_path, llm_provider="openrouter", llm_api_key="k")
    assert build_llm(s).extra_body == {"reasoning": {"enabled": False}}
    s.llm_reasoning = "default"
    assert build_llm(s).extra_body == {}
    assert build_llm(make_settings(tmp_path, llm_provider="openai", llm_api_key="k")).extra_body == {}
    assert build_llm(make_settings(tmp_path, llm_provider="vllm", llm_model="m")).extra_body == {}


def test_reasoning_flag_is_sent_on_the_wire_for_openrouter(server, tmp_path):
    srv = server([{"content": "ok"}])
    OpenAICompatibleClient(srv.url, "k", "m", 5, "openrouter", {}, {"reasoning": {"enabled": False}}).chat([{"role": "user", "content": "x"}], max_tokens=50)
    assert srv.requests[0]["reasoning"] == {"enabled": False} and srv.requests[0]["max_tokens"] == 50


def test_model_that_burns_its_budget_on_reasoning_gives_a_precise_error_and_workflows_fall_back(server, tmp_path):
    import json
    thinking = json.dumps({"choices": [{"finish_reason": "length", "message": {"content": "", "reasoning": "hmm " * 50}}]})
    srv = server([{"raw": thinking}])
    with pytest.raises(LLMUnavailable, match="hidden reasoning"):
        OpenAICompatibleClient(srv.url, "k", "m", 5).chat([{"role": "user", "content": "x"}])
    srv2 = server([{"tool": "wf004_product_description_generator", "args": {}}] + [{"raw": thinking}] * 4)
    r = agent_for(srv2, tmp_path).handle("Generate SEO content for this product.")
    assert r.kind == "completed" and all(m.startswith("template") for m in r.report.result.data["generation_modes"].values())
    assert any("hidden reasoning" in w for w in r.report.warnings)


# ---------------- regression: models invent arguments (live run: inventory_file='inventory.csv') ----------------
def test_invented_file_name_from_the_model_is_dropped_and_the_sample_is_used(server, tmp_path):
    srv = server([{"tool": "wf001_inventory_restock_check", "args": {"inventory_file": "inventory.csv"}}])
    r = agent_for(srv, tmp_path).handle("Which products need restocking?")
    assert r.kind == "completed"
    assert r.report.param_sources["inventory_file"] == "sample" and r.report.params["inventory_file"] == "data/inventory.csv"
    assert "inventory_file='inventory.csv'" in r.route.note


def test_grounded_model_arguments_are_kept(server, tmp_path):
    # file named in the request, existing file, id normalised from digits, number present in the text
    cases = [("restock using data/inventory.csv please", {"inventory_file": "data/inventory.csv"}, "inventory_file"),
             ("restock please", {"inventory_file": "data/inventory.csv"}, "inventory_file"),
             ("products below 15 units", {"threshold": 15}, "threshold")]
    for text, args, key in cases:
        srv = server([{"tool": "wf001_inventory_restock_check", "args": args}])
        r = agent_for(srv, tmp_path).handle(text)
        assert r.report.param_sources.get(key) == "user", (text, r.route.note)
    srv = server([{"tool": "wf005_customer_order_status", "args": {"order_id": "ORD-1003"}}])
    assert agent_for(srv, tmp_path).handle("check 1003 for me").report.params["order_id"] == "ORD-1003"


def test_invented_order_id_and_number_are_dropped(server, tmp_path):
    srv = server([{"tool": "wf005_customer_order_status", "args": {"order_id": "ORD-1003"}}])
    r = agent_for(srv, tmp_path).handle("where is my order")                      # no id anywhere in the request
    assert r.kind == "needs_input" and "order_id" not in r.report.params
    srv = server([{"tool": "wf001_inventory_restock_check", "args": {"threshold": 50}}])
    assert "threshold" not in agent_for(srv, tmp_path).handle("what needs restocking").report.params


def test_array_arguments_keep_only_grounded_items(server, tmp_path):
    srv = server([{"tool": "wf008_seo_keyword_classification", "args": {"keywords": ["buy yoga mat", "invented keyword", "cheap yoga mat"]}}])
    r = agent_for(srv, tmp_path).handle("classify these keywords: buy yoga mat, cheap yoga mat")
    assert r.report.params["keywords"] == ["buy yoga mat", "cheap yoga mat"]
