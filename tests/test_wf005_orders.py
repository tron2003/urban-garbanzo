def run(agent, **p):
    return agent.run_workflow("WF005", p)


def test_shipped_order_with_tracking(agent):
    r = run(agent, order_id="ORD-1001")
    o = r.result.data["orders"][0]
    assert r.status == "success" and o["status"] == "Shipped"
    assert o["shipment"]["tracking_number"] == "DHL-7788123400"
    assert "DHL" in r.result.summary


def test_not_found_asks_for_another_identifier(agent):
    r = run(agent, order_id="ORD-9999")
    assert r.status == "needs_input"
    assert "another identifier" in r.clarification.message
    assert r.steps[1].status == "needs_input" and r.steps[2].status == "skipped"


def test_invalid_identifier_is_rejected_before_searching(agent):
    r = run(agent, order_id="12")
    assert r.status == "needs_input" and "not a valid order ID" in r.clarification.message
    assert not r.tool_calls                      # never touched the order API


def test_no_identifier_asks(agent):
    r = run(agent)
    assert r.status == "needs_input" and r.clarification.missing == ["order_id"]


def test_email_returns_all_orders(agent):
    r = run(agent, customer_email="Ana.Silva@example.com")
    ids = [o["order_id"] for o in r.result.data["orders"]]
    assert ids == ["ORD-1001", "ORD-1006"]


def test_processing_order_has_no_tracking_but_explains(agent):
    o = run(agent, order_id="ORD-1002").result.data["orders"][0]
    assert o["shipment"] is None and "Not shipped yet" in o["shipment_note"]
    assert not any(c.tool == "shipment_lookup" for c in run(agent, order_id="ORD-1002").tool_calls)


def test_cancelled_order(agent):
    o = run(agent, order_id="ORD-1005").result.data["orders"][0]
    assert o["status"] == "Cancelled" and "cancelled" in o["shipment_note"].lower()


def test_transient_shipment_failure_is_retried(agent):
    r = run(agent, order_id="ORD-1004")          # fixture fails once, then succeeds
    assert r.status == "success"
    assert r.result.data["orders"][0]["shipment"]["carrier"] == "UPS"
    call = next(c for c in r.tool_calls if c.tool == "shipment_lookup")
    assert call.status == "retried" and call.attempts == 2


def test_permanent_shipment_outage_degrades_gracefully(agent):
    r = run(agent, order_id="ORD-1007")          # fixture keeps failing
    assert r.status == "success"
    o = r.result.data["orders"][0]
    assert o["status"] == "Shipped" and o["shipment"] is None
    assert "temporarily unavailable" in o["shipment_note"]
    assert any("shipment lookup failed" in w for w in r.warnings)


def test_lowercase_order_id_is_normalised(agent):
    assert run(agent, order_id="ord-1003").result.data["orders"][0]["order_id"] == "ORD-1003"
