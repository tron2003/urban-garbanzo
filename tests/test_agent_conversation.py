import json

from workflow_agent.agent import Session
from workflow_agent.formatting import render_json, render_markdown, render_text


def test_order_not_found_then_bare_answer_completes_the_same_run(agent):
    s = Session()
    r1 = agent.handle("Where is order ORD-9999?", s)
    assert r1.kind == "needs_input" and "another identifier" in r1.message and s.pending_workflow == "WF005"
    r2 = agent.handle("ORD-1003", s)
    assert r2.kind == "completed" and r2.route.method == "continued" and r2.report.workflow_id == "WF005"
    assert s.pending_workflow is None


def test_campaign_brief_collects_goal_and_dates_across_turns_and_keeps_earlier_params(agent):
    s = Session()
    r1 = agent.handle("Create a campaign brief for the new collection.", s)
    assert r1.kind == "needs_input" and r1.report.workflow_id == "WF007"
    r2 = agent.handle("Goal: increase autumn sales, from 2026-11-01 to 2026-11-30, promotion: 15% off", s)
    assert r2.kind == "completed"
    assert r2.report.params["collection"] == "new"                       # remembered from turn 1
    assert len(r2.report.result.data["products"]) == 5 and "15% off" in str(r2.report.params["promotion"])


def test_unrelated_message_while_waiting_is_routed_fresh(agent):
    s = Session()
    agent.handle("Where is order ORD-9999?", s)
    r = agent.handle("Which products need restocking?", s)
    assert r.report.workflow_id == "WF001" and s.pending_workflow is None


def test_bare_text_is_not_swallowed_as_an_answer_when_it_is_a_different_request(agent):
    s = Session()
    agent.handle("Where is order ORD-9999?", s)
    r = agent.handle("find likely duplicate products in the catalog", s)
    assert r.report.workflow_id == "WF006"


def test_ambiguous_request_offers_options_and_accepts_a_number(agent):
    s = Session()
    r = agent.handle("write marketing copy for this item", s)
    assert r.kind == "ambiguous" and [o[0] for o in r.options] == ["WF004", "WF007"]
    assert render_text(r).count("WF00") >= 2
    r2 = agent.handle("1", s)
    assert r2.report.workflow_id == "WF004" and r2.route.method == "user-selected"


def test_out_of_scope_lists_capabilities(agent):
    r = agent.handle("what's the weather like?")
    assert r.kind == "no_match" and all(w in r.message for w in ("WF001", "WF010"))


def test_empty_request_and_unknown_explicit_workflow(agent):
    assert agent.handle("   ").kind == "no_match"
    assert "Unknown workflow" in agent.handle("x", workflow_id="WF999").message


def test_overrides_beat_inferred_values_and_are_coerced(agent):
    r = agent.handle("which products are below 5", overrides={"threshold": "30", "nonsense": "x"})
    assert r.report.params["threshold"] == 30.0 and "nonsense" not in r.report.params


def test_explicit_workflow_skips_routing(agent):
    r = agent.handle("anything", workflow_id="WF010")
    assert r.route.method == "explicit" and r.report.workflow_id == "WF010"


def test_failed_run_clears_pending_state(agent):
    s = Session()
    r = agent.handle("Which products need restocking?", s, overrides={"inventory_file": "missing.csv"})
    assert r.kind == "failed" and s.pending_workflow is None


# ---- renderers ----------------------------------------------------------------------------
def test_text_output_shows_what_the_assignment_asks_for(agent):
    out = render_text(agent.handle("Which products need restocking?"))
    for needle in ("Selected workflow", "Steps executed", "Conditions / decisions", "Tools / API calls", "Result", "SKU-1004"):
        assert needle in out


def test_json_output_is_valid_and_complete(agent):
    d = json.loads(render_json(agent.handle("Where is order ORD-1001?")))
    run = d["run"]
    assert d["routing"]["workflow_id"] == "WF005" and run["status"] == "success"
    assert [s["status"] for s in run["steps"]] == ["success"] * 5
    assert run["result"]["data"]["orders"][0]["shipment"]["carrier"] == "DHL"
    assert {"tool", "operation", "step", "status"} <= set(run["tool_calls"][0])


def test_markdown_tables_and_clarification_rendering(agent):
    md = render_markdown(agent.handle("Find products where vendor price differs by more than 10%."))
    assert "| SKU |" in md and "|---|" in md
    q = render_text(agent.handle("Create a campaign brief for the new collection."))
    assert "I need more information" in q and "ASK" in q
    f = render_text(agent.handle("restock", overrides={"inventory_file": "nope.csv"}))
    assert "could not complete" in f and "Hint:" in f
