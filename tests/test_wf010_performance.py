import csv
from collections import defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent


def independent_stats():
    """Recompute the headline numbers straight from the CSV, without using any agent code."""
    runs = defaultdict(lambda: {"wf": None, "status": None, "ms": 0.0})
    for r in csv.DictReader((ROOT / "data" / "execution_logs.csv").open(encoding="utf-8")):
        run = runs[r["run_id"]]
        run["wf"], run["status"] = r["workflow_id"], r["run_status"]
        run["ms"] += float(r["duration_ms"])
    out = defaultdict(lambda: {"ok": 0, "failed": 0, "ask": 0, "ms": []})
    for run in runs.values():
        o = out[run["wf"]]
        if run["status"] == "success":
            o["ok"] += 1; o["ms"].append(run["ms"])
        elif run["status"] == "failed":
            o["failed"] += 1; o["ms"].append(run["ms"])
        else:
            o["ask"] += 1
    return out


def test_metrics_match_independent_calculation(agent):
    d = agent.run_workflow("WF010").result.data
    for wid, o in independent_stats().items():
        executed = o["ok"] + o["failed"]
        assert d["metrics"][wid]["failed"] == o["failed"]
        assert abs(d["metrics"][wid]["failure_rate"] - round(100 * o["failed"] / executed, 2)) < 0.01
        assert abs(d["metrics"][wid]["avg_ms"] - sum(o["ms"]) / len(o["ms"])) < 0.01


def test_flags(agent):
    d = agent.run_workflow("WF010").result.data
    assert set(d["failure_flagged"]) == {"WF003", "WF004", "WF005"}          # 18.18 %, 17.65 %, 16.00 % (> 10 %)
    assert "WF001" not in d["failure_flagged"]                                # 4.2 %
    assert d["slow_flagged"] == ["WF004"] or set(d["slow_flagged"]) == {"WF004"}


def test_needs_input_runs_are_not_failures(agent):
    d = agent.run_workflow("WF010").result.data
    o = independent_stats()["WF005"]
    assert o["ask"] == 5 and d["metrics"]["WF005"]["failed"] == 4
    assert d["metrics"]["WF005"]["runs"] == 30


def test_worst_workflow_listed_first_and_in_summary(agent):
    r = agent.run_workflow("WF010")
    assert r.result.tables[0].rows[0][0] == "WF003"
    assert "WF003 (18.18%)" in r.result.summary


def test_frequent_errors_and_slow_steps(agent):
    r = agent.run_workflow("WF010")
    top = r.result.data["top_errors"][0]
    assert top["count"] >= 3
    slow = next(t for t in r.result.tables if t.title.startswith("Slow steps"))
    assert any(row[0] == "WF004" for row in slow.rows)
    assert all(float(row[2].replace(",", "")) > 2000 for row in slow.rows)


def test_recommendations_are_specific(agent):
    recs = agent.run_workflow("WF010").result.data["recommendations"]
    joined = "\n".join(recs)
    assert any(r.startswith("[Reliability] WF004") and "back-off" in r for r in recs)   # timeout advice
    assert any(r.startswith("[Reliability] WF003") for r in recs)
    assert any(r.startswith("[Speed] WF004") and "LLM" in r for r in recs)
    assert "WF001" not in joined


def test_thresholds_are_configurable(agent):
    agent.settings.failure_rate_threshold_pct = 20.0
    assert agent.run_workflow("WF010").result.data["failure_flagged"] == []
    agent.settings.failure_rate_threshold_pct = 0.0
    assert "WF001" in agent.run_workflow("WF010").result.data["failure_flagged"]


def test_exactly_at_threshold_is_not_flagged(agent, tmp_path):
    f = tmp_path / "l.csv"
    rows = ["workflow_id,run_id,step_name,step_status,duration_ms,run_status"]
    for i in range(10):            # 1 failure in 10 runs = exactly 10.00 %
        st = "failed" if i == 0 else "success"
        rows.append(f"WFX,r{i},only step,{st},100,{st}")
    f.write_text("\n".join(rows))
    r = agent.run_workflow("WF010", {"log_file": str(f)})
    assert r.result.data["failure_flagged"] == [] and r.result.data["metrics"]["WFX"]["failure_rate"] == 10.0


def test_run_level_log_without_steps(agent, tmp_path):
    f = tmp_path / "l.csv"
    f.write_text("workflow,status,duration\nA,success,100\nA,failed,300\nB,success,50\n")
    r = agent.run_workflow("WF010", {"log_file": str(f)})
    assert r.status == "success" and r.result.data["metrics"]["A"]["failure_rate"] == 50.0
    assert any("no step_name" in w for w in r.warnings)


def test_bad_inputs(agent, tmp_path):
    assert agent.run_workflow("WF010", {"log_file": "nope.csv"}).status == "failed"
    f = tmp_path / "l.csv"; f.write_text("foo,bar\n1,2\n")
    r = agent.run_workflow("WF010", {"log_file": str(f)})
    assert r.status == "failed" and "workflow_id" in r.error


def test_live_logs_before_any_run_fails_cleanly(agent):
    r = agent.run_workflow("WF010", {"live_logs": True})        # fresh agent: nothing has been logged yet
    assert r.status == "failed" and "no live execution log" in r.error


def test_can_analyse_the_agents_own_log(agent):
    agent.run_workflow("WF001"); agent.run_workflow("WF001", {"inventory_file": "missing.csv"})
    r = agent.run_workflow("WF010", {"live_logs": True})
    assert r.status == "success"
    assert r.result.data["metrics"]["WF001"]["runs"] == 2 and r.result.data["metrics"]["WF001"]["failed"] == 1
