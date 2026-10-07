# Loom walkthrough outline (about 8-10 minutes)

Author: Kanish Mahato. Say these in your own words; run everything live.

1. **Problem and approach (30s).** Ten workflows in Excel; requirement: reusable architecture, not ten chatbots.
2. **Architecture (1.5 min).** Show the diagram in the README. Excel = what, Python = how. Engine is generic; only
   `workflows/` knows a workflow. Open `core/engine.py` briefly.
3. **Excel processing (1 min).** `python -m workflow_agent --list`, then `--validate`. Mention fail-fast binding.
4. **Workflow selection (1.5 min).** Explain LLM tool calling (each Excel row = a function) and the TF-IDF fallback.
   Run `"Check today's inventory and identify products that need restocking."`; point to Selected workflow / Why.
   Show an ambiguous request (`write marketing copy for this item`) and an out-of-scope one.
5. **Execution and tools (1.5 min).** Same run: steps, tool calls, decisions beside the Excel rule. Mention the tool
   permission check (`Tools_Required`) and retries.
6. **Conditions and errors (2.5 min).** Live: `Where is order ORD-9999?` then `ORD-1003`; `ORD-1004` (retry);
   `ORD-1007` (graceful degradation); campaign brief asking for goal/dates; vendor file with invalid rows; stock exactly
   at minimum and exactly 10% difference not flagged; WF009 escalation; a missing file.
7. **All 10 working (1 min).** `python -m workflow_agent --examples`, open `examples/outputs/README.md`.
8. **11th workflow (1 min).** Show the snippet in the README / the test; run `--validate`.
9. **Decisions and limits (30s).** No LangGraph and why; interpretations; what was and wasn't tested with a real LLM
   (say honestly whether you ran it against a real model). `python -m pytest` result.
