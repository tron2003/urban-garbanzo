def skus(report):
    return [r["sku"] for r in report.result.data["restock"]]


def test_flags_only_strictly_below_minimum(agent):
    report = agent.run_workflow("WF001")
    assert report.status == "success"
    # SKU-1005 (30 vs min 30) sits exactly at the minimum and must NOT be flagged
    assert set(skus(report)) == {"SKU-1001", "SKU-1003", "SKU-1004", "SKU-1006", "SKU-1008", "SKU-1010"}
    assert "SKU-1005" not in skus(report)


def test_reorder_quantities(agent):
    rows = {r["sku"]: r["reorder_qty"] for r in agent.run_workflow("WF001").result.data["restock"]}
    assert rows["SKU-1001"] == 88      # max 100 - 12
    assert rows["SKU-1004"] == 60      # out of stock: max 60 - 0
    assert rows["SKU-1008"] == 21      # no max_stock: 2 x 12 - 3


def test_invalid_rows_are_reported_not_fatal(agent):
    report = agent.run_workflow("WF001")
    assert report.result.data["evaluated"] == 10
    assert len(report.result.data["skipped"]) == 2
    assert any("SKU-1011" in w and "not a number" in w for w in report.warnings)
    assert any("SKU-1012" in w for w in report.warnings)


def test_most_critical_first(agent):
    assert skus(agent.run_workflow("WF001"))[0] == "SKU-1004"   # zero stock


def test_global_threshold_override(agent):
    report = agent.run_workflow("WF001", {"threshold": 20})
    # with a global minimum of 20: stock<20 -> 1001(12),1003(5),1004(0),1006(8),1008(3),1010(14),1012(9)
    assert "SKU-1012" in skus(report)
    assert "SKU-1002" not in skus(report)


def test_steps_follow_excel_order_and_all_succeed(agent):
    report = agent.run_workflow("WF001")
    assert [s.name for s in report.steps] == [
        "Load inventory", "compare current stock with minimum threshold", "identify low-stock products",
        "calculate reorder quantity", "generate restock list"]
    assert all(s.status == "success" for s in report.steps)
    assert report.result.artifacts


def test_missing_file_fails_cleanly(agent):
    report = agent.run_workflow("WF001", {"inventory_file": "data/does_not_exist.csv"})
    assert report.status == "failed"
    assert "not found" in report.error.lower()
    assert [s.status for s in report.steps][1:] == ["skipped"] * 4


def test_file_without_minimum_column_asks_for_threshold(agent, tmp_path):
    f = tmp_path / "inv.csv"
    f.write_text("sku,name,qty\nA1,Widget,3\nA2,Gadget,50\n")
    report = agent.run_workflow("WF001", {"inventory_file": str(f)})
    assert report.status == "needs_input"
    assert "threshold" in report.clarification.missing
    report2 = agent.run_workflow("WF001", {"inventory_file": str(f), "threshold": 10})
    assert report2.status == "success" and skus(report2) == ["A1"]
