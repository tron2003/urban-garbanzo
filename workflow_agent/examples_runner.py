"""Runs the workbook's Test_Questions plus examples/scenarios.json and saves every result under examples/outputs/."""
from __future__ import annotations

import json
import shutil
from pathlib import Path

from .agent import Agent, Session
from .config import Settings
from .formatting import render_json, render_markdown, render_text


def run_examples(agent: Agent, out_dir: Path | None = None) -> int:
    base = agent.settings.base_dir
    out = out_dir or base / "examples" / "outputs"
    if out.exists():
        for p in out.iterdir():
            if p.name != ".gitkeep":
                shutil.rmtree(p) if p.is_dir() else p.unlink()
    out.mkdir(parents=True, exist_ok=True)
    agent.settings.output_dir = out / "artifacts"
    agent.settings.log_file = out / "execution_log.csv"
    agent.engine.logger.path = agent.settings.log_file

    index = ["# Example runs\n", f"LLM mode: **{getattr(agent.llm, 'name', 'none')}** "
             f"({'LLM tool-calling' if agent.llm.available else 'offline heuristic router + template generation'})\n",
             "## 1. The workbook's own Test_Questions sheet\n", "| Workflow | Request | Selected | Routing | Outcome |", "|---|---|---|---|---|"]
    failures = 0

    def record(name: str, turns: list[str]) -> list:
        session, responses = Session(), []
        for t in turns:
            responses.append(agent.handle(t, session))
        md = "\n\n---\n\n".join(render_markdown(r) for r in responses)
        txt = "\n\n".join(render_text(r, max_rows=25) for r in responses)
        (out / f"{name}.md").write_text(md, encoding="utf-8")
        (out / f"{name}.txt").write_text(txt, encoding="utf-8")
        (out / f"{name}.json").write_text("[" + ",\n".join(render_json(r) for r in responses) + "]", encoding="utf-8")
        return responses

    for s in agent.specs:
        for i, req in enumerate(s.examples, 1):
            name = f"test_question_{s.id}" + (f"_{i}" if len(s.examples) > 1 else "")
            (resp,) = record(name, [req])
            sel = resp.report.workflow_id if resp.report else "-"
            ok = sel == s.id
            failures += 0 if ok else 1
            index.append(f"| {s.id} | {req} | {sel} {'OK' if ok else 'MISMATCH'} | {resp.route.method if resp.route else '-'} | "
                         f"{resp.kind} ([details]({name}.md)) |")

    index += ["", "## 2. Scenarios (edge cases, clarifications, errors)\n", "| Scenario | Turns | Result of last turn |", "|---|---|---|"]
    scenarios = json.loads((base / "examples" / "scenarios.json").read_text(encoding="utf-8"))
    for sc in scenarios:
        resps = record(sc["name"], sc["turns"])
        index.append(f"| [{sc['name']}]({sc['name']}.md) | {len(sc['turns'])} | {' -> '.join(r.kind for r in resps)} |")
    (out / "README.md").write_text("\n".join(index) + "\n", encoding="utf-8")
    print(f"Wrote examples to {out}  (Test_Questions routed correctly: "
          f"{sum(len(s.examples) for s in agent.specs) - failures}/{sum(len(s.examples) for s in agent.specs)})")
    return 1 if failures else 0
