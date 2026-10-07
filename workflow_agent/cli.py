"""Command line interface.

  python -m workflow_agent "Which products need restocking?"        one request
  python -m workflow_agent                                           interactive chat (follow-ups work)
  python -m workflow_agent --list | --validate | --examples
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

from .agent import Agent, Session
from .config import Settings
from .core.errors import WorkflowConfigError
from .formatting import render_json, render_markdown, render_text


def _utf8() -> None:
    for stream in (sys.stdout, sys.stderr):
        try:
            stream.reconfigure(encoding="utf-8", errors="replace")      # Windows consoles default to cp1252
        except Exception:
            pass


def _build(args) -> Agent:
    settings = Settings.from_env()
    if args.no_llm:
        settings.llm_provider = "none"
    if args.excel:
        settings.workflow_excel = Path(args.excel)
    return Agent(settings, strict=not args.allow_partial)


def _print_list(agent: Agent) -> None:
    for s in agent.specs:
        print(f"{s.id}  {s.name}")
        print(f"      trigger : {s.trigger}")
        print(f"      inputs  : {s.inputs}")
        print(f"      steps   : {' -> '.join(s.steps)}")
        print(f"      rule    : {s.decision_logic}")
        print(f"      tools   : {'; '.join(s.tools)}")
        print(f"      output  : {s.expected_output}")
        print()


def _validate(agent: Agent) -> int:
    print(f"Workbook : {agent.settings.workflow_excel}")
    print(f"LLM      : {getattr(agent.llm, 'name', 'none')} ({'available' if agent.llm.available else 'offline mode'})")
    print(f"Tools    : {', '.join(agent.tools.names())}\n")
    for s in agent.specs:
        mod = agent.registry.get(s.id)
        bound = sum(1 for st in s.steps if st.strip().lower() in mod.handlers) if mod else 0
        print(f"  {s.id}  {s.name:<32} steps bound {bound}/{len(s.steps)}   tools: " +
              ", ".join(f"{t}->{agent.tools.resolve(t) or 'MISSING'}" for t in s.tools))
    for w in agent.config_warnings:
        print(f"  warning: {w}")
    if agent.binding_errors:
        print("\nProblems found:")
        for e in agent.binding_errors:
            print(f"  - {e}")
        return 1
    print("\nAll Excel workflows are bound to code and all tools resolve.")
    return 0


def _parse_params(items: list[str]) -> dict[str, str]:
    out = {}
    for it in items or []:
        if "=" not in it:
            raise SystemExit(f"--param expects key=value, got '{it}'")
        k, _, v = it.partition("=")
        out[k.strip()] = v.strip()
    return out


def _show(resp, args) -> None:
    if args.json:
        print(render_json(resp))
    elif args.markdown:
        print(render_markdown(resp))
    else:
        print(render_text(resp, max_rows=args.max_rows))


def _interactive(agent: Agent, args) -> None:
    print("Workflow agent - type a request, '/workflows' to list what I can do, '/exit' to quit.")
    print(f"(LLM: {getattr(agent.llm, 'name', 'none')}{'' if agent.llm.available else ' - offline heuristic mode'})\n")
    session = Session()
    overrides = _parse_params(args.param)
    while True:
        try:
            text = input("you> ").strip()
        except (EOFError, KeyboardInterrupt):
            print()
            return
        if text in ("/exit", "/quit", "exit", "quit"):
            return
        if text == "/workflows":
            _print_list(agent)
            continue
        if not text:
            continue
        resp = agent.handle(text, session, overrides=overrides)
        _show(resp, args)
        print()


def main(argv=None) -> int:
    _utf8()
    ap = argparse.ArgumentParser(prog="workflow_agent", description="Excel-driven AI workflow agent")
    ap.add_argument("request", nargs="*", help="natural-language request (omit for interactive mode)")
    ap.add_argument("--workflow", help="skip routing and run this workflow id (e.g. WF001)")
    ap.add_argument("--param", action="append", default=[], metavar="KEY=VALUE", help="set a workflow parameter explicitly")
    ap.add_argument("--json", action="store_true", help="print the full result as JSON")
    ap.add_argument("--markdown", action="store_true", help="print the result as markdown")
    ap.add_argument("--max-rows", type=int, default=15, help="rows shown per table in text mode")
    ap.add_argument("--no-llm", action="store_true", help="force offline mode (heuristic routing, template generation)")
    ap.add_argument("--excel", help="use a different workflow workbook")
    ap.add_argument("--list", action="store_true", help="list the workflows defined in the workbook")
    ap.add_argument("--validate", action="store_true", help="check that every Excel workflow/step/tool is bound to code")
    ap.add_argument("--examples", action="store_true", help="run the Test_Questions from the workbook and the bundled scenarios")
    ap.add_argument("--allow-partial", action="store_true", help="start even if some workflows are not implemented")
    args = ap.parse_args(argv)

    try:
        agent = _build(args)
    except WorkflowConfigError as exc:
        print("Configuration problem - the Excel workbook and the code disagree:", file=sys.stderr)
        for p in exc.problems:
            print(f"  - {p}", file=sys.stderr)
        return 2

    if args.list:
        _print_list(agent)
        return 0
    if args.validate:
        return _validate(agent)
    if args.examples:
        from .examples_runner import run_examples
        return run_examples(agent)

    overrides = _parse_params(args.param)
    if args.request or args.workflow:
        resp = agent.handle(" ".join(args.request), overrides=overrides, workflow_id=args.workflow)
        _show(resp, args)
        return 0 if resp.kind in ("completed", "needs_input", "ambiguous") else 1
    _interactive(agent, args)
    return 0


def entry() -> int:
    try:
        return main()
    except BrokenPipeError:        # e.g. piping into `head`
        return 0


if __name__ == "__main__":
    sys.exit(entry())
