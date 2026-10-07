import pytest
from openpyxl import Workbook

from workflow_agent.core.errors import WorkflowConfigError
from workflow_agent.excel_loader import load_workflow_specs, norm_key

HEAD = ["Workflow_ID", "Workflow_Name", "Trigger", "Inputs", "Steps", "Decision_Logic", "Tools_Required", "Expected_Output"]


def make(tmp_path, rows, head=HEAD, sheet="Workflows"):
    wb = Workbook(); ws = wb.active; ws.title = sheet
    ws.append(head)
    for r in rows:
        ws.append(r)
    p = tmp_path / "wf.xlsx"; wb.save(p)
    return p


def test_real_workbook_has_ten_workflows_with_examples():
    from tests.conftest import ROOT
    specs = load_workflow_specs(ROOT / "data" / "AI_Agent_Workflow_Assessment.xlsx")
    assert [s.id for s in specs] == [f"WF{i:03d}" for i in range(1, 11)]
    assert all(s.steps and s.tools and s.decision_logic for s in specs)
    assert specs[4].examples == ("Where is order ORD-1001?",)           # from the Test_Questions sheet
    assert specs[0].steps[0] == "Load inventory" and len(specs[2].steps) == 6


def test_arrow_variants_and_tool_splitting(tmp_path):
    p = make(tmp_path, [["W1", "Name", "t", "i", "a -> b → c => d", "rule", "CSV reader; calculator", "out"]])
    (s,) = load_workflow_specs(p)
    assert s.steps == ("a", "b", "c", "d") and s.tools == ("CSV reader", "calculator")


def test_header_case_and_spacing_is_forgiven(tmp_path):
    p = make(tmp_path, [["W1", "N", "t", "i", "a → b", "r", "x", "o"]], head=[h.lower().replace("_", " ") for h in HEAD])
    assert load_workflow_specs(p)[0].id == "W1"


def test_missing_column_is_reported(tmp_path):
    p = make(tmp_path, [["W1", "N"]], head=["Workflow_ID", "Workflow_Name"])
    with pytest.raises(WorkflowConfigError, match="missing column.*steps"):
        load_workflow_specs(p)


def test_duplicate_ids_and_empty_steps_reported_together(tmp_path):
    p = make(tmp_path, [["W1", "A", "t", "i", "s1 → s2", "r", "x", "o"], ["W1", "B", "t", "i", "s1", "r", "x", "o"],
                        ["W2", "C", "t", "i", "", "r", "x", "o"]])
    with pytest.raises(WorkflowConfigError) as e:
        load_workflow_specs(p)
    assert any("duplicate" in x for x in e.value.problems) and any("W2: Steps column is empty" in x for x in e.value.problems)


def test_missing_file_wrong_sheet_and_corrupt_file(tmp_path):
    with pytest.raises(WorkflowConfigError, match="not found"):
        load_workflow_specs(tmp_path / "nope.xlsx")
    with pytest.raises(WorkflowConfigError, match="Sheet 'Workflows' not found"):
        load_workflow_specs(make(tmp_path, [], sheet="Other"))
    bad = tmp_path / "bad.xlsx"; bad.write_text("not a workbook")
    with pytest.raises(WorkflowConfigError, match="Cannot open"):
        load_workflow_specs(bad)


def test_norm_key():
    assert norm_key("  Load   INVENTORY ") == "load inventory"
