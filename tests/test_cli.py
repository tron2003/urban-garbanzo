import json

import pytest

from workflow_agent.cli import main


@pytest.fixture(autouse=True)
def isolate(tmp_path, monkeypatch):
    monkeypatch.setenv("EXECUTION_LOG_FILE", str(tmp_path / "log.csv"))
    monkeypatch.setenv("OUTPUT_DIR", str(tmp_path / "out"))
    monkeypatch.setenv("LLM_PROVIDER", "none")
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)


def test_validate_and_list(capsys):
    assert main(["--validate"]) == 0
    assert "All Excel workflows are bound" in capsys.readouterr().out
    assert main(["--list"]) == 0
    out = capsys.readouterr().out
    assert "WF010" in out and "Employee/task database" in out


def test_single_request_text_and_json(capsys):
    assert main(["Where", "is", "order", "ORD-1001?"]) == 0
    assert "Selected workflow : WF005" in capsys.readouterr().out
    assert main(["Where is order ORD-1001?", "--json"]) == 0
    assert json.loads(capsys.readouterr().out)["run"]["workflow_id"] == "WF005"


def test_param_and_workflow_flags(capsys):
    assert main(["--workflow", "WF001", "--param", "threshold=30", "x"]) == 0
    assert "global threshold 30" in capsys.readouterr().out
    with pytest.raises(SystemExit):
        main(["--param", "oops", "x"])


def test_exit_codes(capsys):
    assert main(["Which products need restocking?", "--param", "inventory_file=missing.csv"]) == 1
    assert main(["what's the weather"]) == 1
    assert main(["Create a campaign brief for the new collection."]) == 0          # asking a question is not an error


def test_broken_workbook_reports_problems_and_exit_2(capsys, tmp_path):
    from openpyxl import Workbook
    wb = Workbook(); wb.active.title = "Workflows"; wb.active.append(["Workflow_ID"]); wb.save(tmp_path / "bad.xlsx")
    assert main(["--excel", str(tmp_path / "bad.xlsx"), "--list"]) == 2
    assert "missing column" in capsys.readouterr().err


def test_interactive_session_supports_follow_ups(capsys, monkeypatch):
    inputs = iter(["Where is order ORD-9999?", "ORD-1002", "/workflows", "/exit"])
    monkeypatch.setattr("builtins.input", lambda _="": next(inputs))
    assert main([]) == 0
    out = capsys.readouterr().out
    assert "another identifier" in out and "ORD-1002 is processing" in out


def test_examples_runner_routes_all_test_questions(capsys, tmp_path):
    from workflow_agent.agent import Agent
    from workflow_agent.config import Settings
    from workflow_agent.examples_runner import run_examples
    a = Agent(Settings.from_env())
    assert run_examples(a, tmp_path / "ex") == 0
    assert (tmp_path / "ex" / "README.md").exists() and (tmp_path / "ex" / "test_question_WF005.json").exists()
