def test_exceptions_over_ten_percent(agent):
    report = agent.run_workflow("WF002")
    assert report.status == "success"
    d = report.result.data
    assert {e["sku"] for e in d["exceptions"]} == {"SKU-1002", "SKU-1004", "SKU-1008"}


def test_exactly_ten_percent_is_not_flagged(agent):
    # SKU-1003: 79.00 vs 71.10 is exactly -10.00%; the rule is "exceeds 10%"
    report = agent.run_workflow("WF002")
    assert "SKU-1003" not in {e["sku"] for e in report.result.data["exceptions"]}
    assert any(d.name == "difference exactly at threshold" for d in report.decisions)


def test_sku_matching_is_case_and_space_insensitive(agent):
    # vendor file has ' sku-1002 '
    report = agent.run_workflow("WF002")
    assert "SKU-1002" in {e["sku"] for e in report.result.data["exceptions"]}


def test_unmatched_and_uncomparable_are_reported(agent):
    d = agent.run_workflow("WF002").result.data
    assert d["unmatched_internal"] == ["SKU-1009"]
    assert d["unmatched_vendor"] == ["SKU-9999"]
    assert set(d["not_comparable"]) == {"SKU-1011", "SKU-1012"}   # vendor 'N/A', internal price 0 (no divide by zero)


def test_custom_threshold(agent):
    d = agent.run_workflow("WF002", {"threshold_pct": 5}).result.data
    assert {"SKU-1003", "SKU-1006"} <= {e["sku"] for e in d["exceptions"]}


def test_no_matching_skus_fails_with_hint(agent, tmp_path):
    a = tmp_path / "a.csv"; a.write_text("sku,name,price\nX1,Thing,10\n")
    b = tmp_path / "b.csv"; b.write_text("sku,vendor_price\nY9,10\n")
    report = agent.run_workflow("WF002", {"product_file": str(a), "vendor_file": str(b)})
    assert report.status == "failed" and "No SKUs match" in report.error
    assert report.steps[-1].status == "skipped"
