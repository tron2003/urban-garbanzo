"""Generate data/execution_logs.csv: realistic, deterministic (seeded) step-level execution logs for WF010.

The schema is the one the agent itself writes to logs/execution_log.csv, so WF010 can analyse either.
Run:  python scripts/generate_sample_logs.py
"""
import csv
import random
import sys
from datetime import datetime, timedelta
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
from workflow_agent.excel_loader import load_workflow_specs  # noqa: E402

COLUMNS = ["timestamp", "run_id", "workflow_id", "workflow_name", "step_name", "step_status", "duration_ms",
           "run_status", "error_type", "error_message"]

# runs, failures, needs_input, base ms per step (default), per-step overrides {index: ms}, failing step index, error
PROFILE = {
    "WF001": dict(runs=24, fails=1, needs=1, base=120, slow={}, fail_step=0, error=("ToolError", "File not found: inventory.csv")),
    "WF002": dict(runs=20, fails=1, needs=0, base=140, slow={}, fail_step=1, error=("StepError", "No SKUs match between the product file and the vendor price list.")),
    "WF003": dict(runs=22, fails=4, needs=0, base=260, slow={0: 700}, fail_step=1,
                  error=("StepError", "Cannot find the required column(s): sku."), alt_error=(0, ("ToolError", "unsupported file type '.xls' (use .csv or .xlsx)"))),
    "WF004": dict(runs=18, fails=3, needs=1, base=500, slow={1: 4200, 2: 3600, 3: 3200, 4: 3400}, fail_step=1,
                  error=("TransientToolError", "llm: LLM endpoint unreachable: timed out")),
    "WF005": dict(runs=30, fails=4, needs=5, base=180, slow={3: 1700}, fail_step=3,
                  error=("TransientToolError", "shipment_lookup: carrier API timed out (simulated)")),
    "WF006": dict(runs=12, fails=0, needs=0, base=210, slow={3: 2900}, fail_step=0, error=("StepError", "Need at least two products")),
    "WF007": dict(runs=14, fails=1, needs=3, base=450, slow={3: 1900}, fail_step=2, error=("StepError", "No products matched (collection contains 'summer').")),
    "WF008": dict(runs=16, fails=1, needs=0, base=300, slow={2: 2300}, fail_step=0, error=("ToolError", "File not found: keywords.csv")),
    "WF009": dict(runs=15, fails=0, needs=2, base=240, slow={}, fail_step=0, error=("StepError", "Could not load the employee data")),
    "WF010": dict(runs=8, fails=0, needs=0, base=160, slow={}, fail_step=0, error=("StepError", "Log file is empty")),
}


def main() -> None:
    rng = random.Random(42)
    specs = {s.id: s for s in load_workflow_specs(ROOT / "data" / "AI_Agent_Workflow_Assessment.xlsx")}
    start = datetime(2026, 9, 1, 8, 0)
    rows, run_no = [], 0
    for wid, p in PROFILE.items():
        spec = specs[wid]
        kinds = ["failed"] * p["fails"] + ["needs_input"] * p["needs"] + ["success"] * (p["runs"] - p["fails"] - p["needs"])
        rng.shuffle(kinds)
        alt_used = False
        for kind in kinds:
            run_no += 1
            ts = start + timedelta(hours=rng.randint(0, 24 * 34), minutes=rng.randint(0, 59))
            run_id = f"{ts:%Y%m%d-%H%M%S}-{run_no:04d}"
            stop_at = None
            err = ("", "")
            if kind == "failed":
                stop_at, err = p["fail_step"], p["error"]
                if "alt_error" in p and not alt_used:
                    stop_at, err = p["alt_error"][0], p["alt_error"][1]
                    alt_used = True
            elif kind == "needs_input":
                stop_at, err = 0, ("NeedMoreInput", "Missing input - asked the user")
            for i, step in enumerate(spec.steps):
                if stop_at is not None and i > stop_at:
                    status, dur, et, em = "skipped", 0.0, "", ""
                else:
                    base = p["slow"].get(i, p["base"])
                    dur = max(5.0, rng.gauss(base, base * 0.18))
                    status, et, em = "success", "", ""
                    if stop_at is not None and i == stop_at:
                        status = "failed" if kind == "failed" else "needs_input"
                        et, em = err
                        dur *= 0.6 if kind == "needs_input" else 1.0
                rows.append({"timestamp": ts.isoformat(timespec="seconds"), "run_id": run_id, "workflow_id": wid,
                             "workflow_name": spec.name, "step_name": step, "step_status": status,
                             "duration_ms": round(dur, 1), "run_status": kind, "error_type": et, "error_message": em})
    rows.sort(key=lambda r: (r["timestamp"], r["run_id"]))
    out = ROOT / "data" / "execution_logs.csv"
    with out.open("w", newline="", encoding="utf-8") as fh:
        w = csv.DictWriter(fh, fieldnames=COLUMNS)
        w.writeheader()
        w.writerows(rows)
    print(f"wrote {len(rows)} step rows for {run_no} runs -> {out}")


if __name__ == "__main__":
    main()
