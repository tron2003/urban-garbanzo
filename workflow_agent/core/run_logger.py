"""Append-only step-level execution log. The schema is the same one WF010 reads,
so the agent's own history can be fed back into the performance-report workflow."""
from __future__ import annotations

import csv
from datetime import datetime
from pathlib import Path

LOG_COLUMNS = ["timestamp", "run_id", "workflow_id", "workflow_name", "step_name",
               "step_status", "duration_ms", "run_status", "error_type", "error_message"]


class RunLogger:
    def __init__(self, path: Path | None):
        self.path = Path(path) if path else None

    def log(self, report) -> None:
        if self.path is None:
            return
        try:
            self.path.parent.mkdir(parents=True, exist_ok=True)
            new = not self.path.exists() or self.path.stat().st_size == 0
            ts = datetime.now().isoformat(timespec="seconds")
            with self.path.open("a", newline="", encoding="utf-8") as fh:
                w = csv.DictWriter(fh, fieldnames=LOG_COLUMNS)
                if new:
                    w.writeheader()
                for s in report.steps:
                    if s.status in ("pending",):
                        continue
                    w.writerow({
                        "timestamp": ts, "run_id": report.run_id, "workflow_id": report.workflow_id,
                        "workflow_name": report.workflow_name, "step_name": s.name,
                        "step_status": s.status, "duration_ms": round(s.duration_ms, 1),
                        "run_status": report.status, "error_type": s.error_type,
                        "error_message": s.error[:300],
                    })
        except OSError:
            pass   # logging must never break a run
