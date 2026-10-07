import csv
from pathlib import Path


def test_csv_invalid_rows(agent):
    report = agent.run_workflow("WF003")
    assert report.status == "success"
    d = report.result.data
    # rows missing SKU (Thermal Socks) or name (V-004) are the only invalid ones; blank row ignored
    assert [r["source_row"] for r in d["invalid"]] == [4, 5]
    assert "missing sku" in d["invalid"][0]["reasons"]
    assert "missing product name" in d["invalid"][1]["reasons"]
    assert d["total"] == 8 and d["valid"] == 6


def test_column_names_are_normalized(agent):
    d = agent.run_workflow("WF003").result.data
    assert d["columns"][:5] == ["sku", "product_name", "price", "quantity", "brand"]


def test_cleaned_file_contents(agent, settings):
    report = agent.run_workflow("WF003")
    cleaned = Path(settings.base_dir / report.result.artifacts[0])
    rows = list(csv.DictReader(cleaned.open(encoding="utf-8")))
    by_sku = {r["sku"]: r for r in rows}
    assert by_sku["V-002"]["product_name"] == "Fleece Gloves"      # whitespace trimmed
    assert by_sku["V-009"]["sku"] == "V-009"                       # upper-cased
    assert by_sku["V-009"]["price"] == "8.40"                      # '$8.40' parsed
    assert by_sku["V-005"]["price"] == ""                          # 'N/A' blanked, row kept


def test_warnings_for_duplicates_and_bad_prices(agent):
    report = agent.run_workflow("WF003")
    assert any("Duplicate SKU" in w and "V-001" in w for w in report.warnings)
    assert any("Non-numeric price" in w for w in report.warnings)


def test_xlsx_with_preamble_rows(agent):
    report = agent.run_workflow("WF003", {"vendor_file": "data/vendor_file.xlsx"})
    assert report.status == "success"
    d = report.result.data
    assert d["valid"] == 3 and len(d["invalid"]) == 2
    assert "sku" in d["columns"] and "price" in d["columns"]
    assert "skipped 3 preamble" in report.steps[0].detail


def test_missing_required_column_fails_with_hint(agent, tmp_path):
    f = tmp_path / "v.csv"; f.write_text("Foo,Bar\n1,2\n")
    report = agent.run_workflow("WF003", {"vendor_file": str(f)})
    assert report.status == "failed"
    assert "sku" in report.error and "Columns found" in report.error_hint


def test_unsupported_and_missing_files(agent, tmp_path):
    f = tmp_path / "v.pdf"; f.write_text("x")
    assert agent.run_workflow("WF003", {"vendor_file": str(f)}).status == "failed"
    assert "not found" in agent.run_workflow("WF003", {"vendor_file": "nope.csv"}).error.lower()


def test_empty_file(agent, tmp_path):
    f = tmp_path / "e.csv"; f.write_text("")
    assert agent.run_workflow("WF003", {"vendor_file": str(f)}).status == "failed"
