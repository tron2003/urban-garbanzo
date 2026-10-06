"""LLM tools: free-form generation and intent classification (rules + optional LLM)."""
from __future__ import annotations

import json
import re
from typing import Any

from ..core.errors import LLMUnavailable, ToolError, TransientToolError
from .registry import tool


def extract_json(text: str) -> Any:
    """Parse JSON that may be wrapped in ```fences``` or prose."""
    cleaned = re.sub(r"^```(?:json)?|```$", "", (text or "").strip(), flags=re.M).strip()
    try:
        return json.loads(cleaned)
    except json.JSONDecodeError:
        m = re.search(r"(\{.*\}|\[.*\])", cleaned, re.S)
        if m:
            try:
                return json.loads(m.group(1))
            except json.JSONDecodeError:
                pass
    raise ToolError("llm", "model did not return valid JSON")


@tool("llm", aliases=("LLM",), description="Text / JSON generation with the configured model.")
def llm_tool(svc, op: str, prompt: str, system: str = "", max_tokens: int = 400) -> Any:
    client = svc.llm
    if not getattr(client, "available", False):
        raise ToolError("llm", "no LLM configured")
    messages = ([{"role": "system", "content": system}] if system else []) + [{"role": "user", "content": prompt}]
    try:
        resp = client.chat(messages, json_mode=(op == "json"), temperature=0.3, max_tokens=max_tokens)
    except LLMUnavailable as exc:
        if exc.transient:
            raise TransientToolError("llm", str(exc)) from exc
        raise ToolError("llm", str(exc)) from exc
    if op == "json":
        return extract_json(resp.content)
    text = (resp.content or "").strip()
    if not text:
        raise ToolError("llm", "model returned an empty answer")
    return text


# ---------------------------------------------------------------- classifier
_NAV = re.compile(r"\b(login|log in|sign in|signin|official site|official website|website|homepage|contact us|customer service|\.com|\.net|\.org|my account|track order)\b", re.I)
_TRANS = re.compile(r"\b(buy|purchase|order|shop|shopping|for sale|discount|coupon|promo code|deal|deals|cheap|cheapest|sale|free shipping|near me|where to buy|add to cart)\b", re.I)
_COMM = re.compile(r"\b(best|top|review|reviews|vs|versus|compare|comparison|alternative|alternatives|recommended|worth it|price|prices|cost|affordable|rated|ranking)\b", re.I)
_INFO = re.compile(r"\b(how|what|why|when|who|which|guide|tutorial|tips|ideas|learn|meaning|definition|difference|examples?|benefits|ways to|steps|diy|can i|should i|does)\b", re.I)


def rule_intent(keyword: str, brands: tuple[str, ...] = ()) -> tuple[str, float]:
    k = keyword.lower()
    if _NAV.search(k) or any(re.search(rf"\b{re.escape(b.lower())}\b", k) for b in brands):
        return "navigational", 0.85
    if _TRANS.search(k):
        return "transactional", 0.85
    if _COMM.search(k):
        return "commercial", 0.8
    if _INFO.search(k):
        return "informational", 0.85
    # bare product phrase ("running shoes"): commercial investigation, but a weak signal
    return "commercial", 0.45


INTENTS = ("informational", "commercial", "transactional", "navigational")


@tool("llm_classifier", aliases=("LLM/classifier",),
      description="Search-intent classifier: rules first, LLM only for low-confidence keywords.")
def llm_classifier(svc, op: str, keywords: list[str], brands: tuple[str, ...] = (), threshold: float = 0.6) -> list[dict]:
    if op != "classify_intent":
        raise ToolError("llm_classifier", f"unsupported op '{op}'")
    results = []
    for kw in keywords:
        intent, conf = rule_intent(kw, brands)
        results.append({"keyword": kw, "intent": intent, "confidence": conf, "source": "rules"})

    uncertain = [r for r in results if r["confidence"] < threshold]
    if uncertain and getattr(svc.llm, "available", False):
        prompt = ("Classify the search intent of each keyword as exactly one of: informational, commercial, "
                  "transactional, navigational. Reply with JSON {\"results\": [{\"keyword\": str, \"intent\": str}]}.\n"
                  "Keywords:\n" + "\n".join(f"- {r['keyword']}" for r in uncertain))
        try:
            resp = svc.llm.chat([{"role": "user", "content": prompt}], json_mode=True, temperature=0.0)
            data = extract_json(resp.content)
            by_kw = {str(x.get("keyword", "")).lower(): str(x.get("intent", "")).lower()
                     for x in (data.get("results") if isinstance(data, dict) else data) or []}
            for r in uncertain:
                label = by_kw.get(r["keyword"].lower())
                if label in INTENTS:
                    r.update(intent=label, confidence=0.75, source="llm")
        except (LLMUnavailable, ToolError):
            pass   # keep rule-based labels; the workflow reports the source per keyword
    return results
