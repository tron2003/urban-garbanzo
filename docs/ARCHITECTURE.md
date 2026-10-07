# Architecture notes

Author: Kanish Mahato

## Components and responsibilities

| Component | File | Responsibility | Knows about specific workflows? |
|---|---|---|---|
| Workbook loader | `excel_loader.py` | Excel -> `WorkflowSpec` | no |
| Registry + validation | `core/registry.py` | binds Excel step text to handlers; startup consistency check | no |
| Engine | `core/engine.py` | runs steps in Excel order, timing, status, error classification, skip-after-stop, run log | no |
| Context | `core/context.py` | what a step may do: params, tools, decisions, warnings, result, artifacts | no |
| Tool registry | `tools/registry.py` | permission (Excel Tools_Required), retry, wrapping, tracing | no |
| Router | `router.py` | pick workflow + params (LLM tool call, heuristic fallback) | only through registered params/hints |
| Agent | `agent.py` | conversation state, clarification, ambiguity, explicit overrides | no |
| Renderers | `formatting.py` | text / markdown / JSON | no |
| Workflow modules | `workflows/wf0xx_*.py` | step logic for one workflow | yes (only place) |

Only `workflows/` and `tools/` grow when the business grows.

## Step outcomes

* success - continue
* `NeedMoreInput` - stop, status `needs_input`, question returned, partially collected parameters kept in the session
* `StepError` / `ToolError` - stop, status `failed`, message + hint, remaining steps `skipped`
* any other exception - treated as failed, never propagates out of the engine
* a successful run must call `ctx.set_result(...)`, otherwise it is reported as failed

## Why decisions are first-class

`ctx.decide(name, outcome, detail)` records each branch the Excel Decision_Logic describes (flagged / not flagged,
asked for input, escalated, fallback used). The renderer prints them next to the Excel rule so a reviewer can see the rule
being applied, including boundary cases such as "exactly 10% is not flagged".

## Logging loop

The engine appends one row per step to `logs/execution_log.csv` using the schema WF010 reads, so
`python -m workflow_agent "performance report on the live logs"` analyses the agent's own history.
