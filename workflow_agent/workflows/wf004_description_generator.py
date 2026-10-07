"""WF004 - Product Description Generator.

Rule (from Excel): do not invent missing product attributes; explicitly mark missing information.

Design:
  * the model only ever sees the attributes that were actually supplied;
  * missing attributes are listed in the result and shown as "[NOT PROVIDED]" in the spec block;
  * every generated text is checked (length, placeholders, and "unsupported claim" words such as a
    material or colour that was never supplied); failures are retried once, then replaced by a
    deterministic template so the workflow never returns invented facts.
"""
from __future__ import annotations

import json
import re

from ..core.errors import NeedMoreInput, ToolError
from ..core.models import Param, Table
from ..core.registry import WorkflowModule
from .common import kv_extractor

FIELDS = ["product_name", "category", "attributes", "material", "color", "target_audience"]
LABELS = {"product_name": "product name", "category": "category", "attributes": "attributes",
          "material": "material", "color": "color", "target_audience": "target audience"}
KEYS = {
    "product_name": ["product name", "product", "name"], "category": ["category"],
    "attributes": ["attributes", "features", "attribute"], "material": ["material", "made of", "made from"],
    "color": ["color", "colour"], "target_audience": ["target audience", "audience"],
}
ALL_KEYS = [k for ks in KEYS.values() for k in ks]
GROUP = "product"


def _p(name, desc, sample=None, typ="string"):
    return Param(name, desc, type=typ, sample_default=sample, sample_group=GROUP,
                 extractor=kv_extractor(KEYS[name], ALL_KEYS), items="string")


wf = WorkflowModule(
    "WF004",
    params=[
        _p("product_name", "Product name", "TrailLite Hiking Backpack 30L"),
        _p("category", "Product category", "Outdoor Gear"),
        _p("attributes", "Key product attributes/features (list)",
           ["30-liter capacity", "padded shoulder straps", "rain cover included"], "array"),
        _p("material", "Material (leave empty if unknown - never guess)"),
        _p("color", "Colour", "Forest Green"),
        _p("target_audience", "Target audience (leave empty if unknown - never guess)"),
    ],
    routing_hints=["seo content", "product description", "meta description", "seo title", "product copy",
                   "write copy", "generate content for product", "short description"],
)

_MATERIALS = ["cotton", "leather", "nylon", "polyester", "wool", "silk", "steel", "aluminium", "aluminum", "plastic",
              "canvas", "denim", "linen", "rubber", "wood", "bamboo", "glass", "ceramic", "titanium", "fleece", "suede", "mesh"]
_COLORS = ["red", "blue", "green", "black", "white", "grey", "gray", "yellow", "orange", "purple", "pink", "brown",
           "silver", "gold", "navy", "beige", "teal"]
_AUDIENCES = ["men", "women", "kids", "children", "teens", "beginners", "professionals", "athletes", "students",
              "families", "seniors", "travellers", "travelers", "commuters", "hikers", "runners"]

SYSTEM = ("You are an e-commerce copywriter. Use ONLY the product facts provided. Never invent or imply any "
          "attribute that is not listed (no materials, colours, sizes, audiences, certifications or performance "
          "claims). If a fact is not listed, do not mention it. Output plain text only, no quotes, no markdown.")


def _facts(ctx) -> dict:
    return ctx.state["facts"]


def _facts_text(f: dict) -> str:
    return "\n".join(f"- {LABELS[k]}: {', '.join(v) if isinstance(v, list) else v}" for k, v in f.items())


def _forbidden(ctx) -> list[str]:
    """Words that would be an invented attribute because the matching field is missing."""
    supplied = " ".join(json.dumps(_facts(ctx)).lower().split())
    out: list[str] = []
    for field, vocab in (("material", _MATERIALS), ("color", _COLORS), ("target_audience", _AUDIENCES)):
        if field in ctx.state["missing"]:
            out += [w for w in vocab if not re.search(rf"\b{w}\b", supplied)]
    return out


def _generate(ctx, field: str, instruction: str, limit: int, template: str) -> str:
    """LLM first (with validation + one retry), deterministic template otherwise."""
    modes = ctx.state.setdefault("modes", {})
    if not ctx.llm_available:
        modes[field] = "template (no LLM configured)"
        return template
    forbidden, feedback, reason = _forbidden(ctx), "", ""
    for _ in range(2):
        prompt = f"Product facts:\n{_facts_text(_facts(ctx))}\n\nTask: {instruction}{feedback}"
        try:
            text = ctx.call_tool("llm", op="text", system=SYSTEM, prompt=prompt, max_tokens=300).strip().strip("\"'")
        except ToolError as exc:
            reason = f"LLM call failed: {exc.message}"
            break
        check = ctx.call_tool("text_validation", op="check", text=text, max_length=limit, forbidden_terms=forbidden)
        if check["ok"]:
            modes[field] = "LLM"
            return text
        if all(i.startswith("too long") for i in check["issues"]):
            modes[field] = "LLM (trimmed to length limit)"
            return ctx.call_tool("text_validation", op="truncate", text=text, limit=limit)
        reason = "; ".join(check["issues"])
        feedback = f"\n\nYour previous answer was rejected: {reason}. Rewrite it using only the listed facts."
    ctx.warn(f"{LABELS.get(field, field)}: LLM output rejected ({reason}); used the deterministic template instead")
    modes[field] = "template (LLM output failed validation)"
    return template


@wf.step("Validate required attributes")
def validate(ctx):
    facts, missing = {}, []
    for f in FIELDS:
        v = ctx.param(f)
        if v in (None, "", []):
            missing.append(f)
        else:
            facts[f] = v
    if "product_name" in missing:
        raise NeedMoreInput("I need at least the product name. Please give the product details, e.g. "
                            "'product name: ...; category: ...; material: ...; color: ...; target audience: ...; "
                            "attributes: ..., ...'.", ["product_name"])
    ctx.state.update(facts=facts, missing=missing, modes={})
    ctx.decide("missing attributes", "marked as missing, not invented" if missing else "none missing",
               ", ".join(LABELS[m] for m in missing) or "all six attributes supplied")
    if missing:
        ctx.warn("Missing information (not invented): " + ", ".join(LABELS[m] for m in missing))
    src = " (bundled sample product)" if ctx.source("product_name") == "sample" else ""
    return f"{len(facts)} of {len(FIELDS)} attributes supplied{src}; missing: {', '.join(LABELS[m] for m in missing) or 'none'}"


@wf.step("create product description")
def description(ctx):
    f = _facts(ctx)
    parts = [f"{f['product_name']}" + (f" is a {f['category']} product." if "category" in f else " is a product.")]
    if "attributes" in f:
        feats = f["attributes"]
        parts.append("Key features: " + (", ".join(feats[:-1]) + " and " + feats[-1] if len(feats) > 1 else feats[0]) + ".")
    if "material" in f:
        parts.append(f"It is made from {f['material']}.")
    if "color" in f:
        parts.append(f"Available in {f['color']}.")
    if "target_audience" in f:
        parts.append(f"Designed for {f['target_audience']}.")
    body = _generate(ctx, "description",
                     "Write a product description of 2-4 sentences (max 600 characters) for a product page.", 600, " ".join(parts))
    spec = ["", "Specifications:"] + [
        f"- {LABELS[k].capitalize()}: " + (", ".join(f[k]) if isinstance(f.get(k), list) else f[k])
        if k in f else f"- {LABELS[k].capitalize()}: [NOT PROVIDED]" for k in FIELDS[1:]]
    ctx.state["description"] = body + "\n" + "\n".join(spec)
    ctx.state["description_body"] = body
    return f"Description created via {ctx.state['modes']['description']} ({len(body)} chars)"


@wf.step("generate short description")
def short(ctx):
    f = _facts(ctx)
    bits = [f["product_name"]]
    if "attributes" in f:
        bits.append(", ".join(f["attributes"][:2]))
    if "color" in f:
        bits.append(f["color"])
    template = ctx.call_tool("text_validation", op="truncate", text=": ".join(bits[:2]) + (f" - {bits[2]}" if len(bits) > 2 else ""), limit=160)
    ctx.state["short"] = _generate(ctx, "short", "Write ONE short description sentence, max 160 characters.", 160, template)
    return f"{len(ctx.state['short'])} chars via {ctx.state['modes']['short']}"


@wf.step("generate SEO title")
def seo_title(ctx):
    f = _facts(ctx)
    base = f["product_name"] + (f" | {f['category']}" if "category" in f else "")
    template = base if len(base) <= 60 else ctx.call_tool("text_validation", op="truncate", text=f["product_name"], limit=60)
    ctx.state["seo_title"] = _generate(ctx, "seo_title", "Write an SEO page title, max 60 characters, including the product name.", 60, template)
    return f"{len(ctx.state['seo_title'])}/60 chars via {ctx.state['modes']['seo_title']}"


@wf.step("generate meta description")
def meta(ctx):
    f = _facts(ctx)
    bits = [f"Discover the {f['product_name']}."]
    if "attributes" in f:
        bits.append(", ".join(f["attributes"][:3]).capitalize() + ".")
    if "color" in f:
        bits.append(f"Available in {f['color']}.")
    template = ctx.call_tool("text_validation", op="truncate", text=" ".join(bits), limit=155)
    ctx.state["meta"] = _generate(ctx, "meta", "Write an SEO meta description, max 155 characters.", 155, template)

    m = ctx.state["modes"]
    missing = [LABELS[x] for x in ctx.state["missing"]]
    rows = [["Short description", len(ctx.state["short"]), "160", m["short"]],
            ["SEO title", len(ctx.state["seo_title"]), "60", m["seo_title"]],
            ["Meta description", len(ctx.state["meta"]), "155", m["meta"]],
            ["Product description", len(ctx.state["description_body"]), "600", m["description"]]]
    tables = [Table("Generated content", ["Field", "Length", "Limit", "Generated by"], rows)]
    if missing:
        tables.append(Table("Missing information (not invented)", ["Attribute", "Status"], [[x, "NOT PROVIDED"] for x in missing]))
    ctx.set_result(
        f"Generated description, short description, SEO title and meta description for '{_facts(ctx)['product_name']}'"
        + (f"; {len(missing)} attribute(s) were missing and were marked, not invented." if missing else "."),
        tables=tables,
        text_blocks=[("Product description", ctx.state["description"]), ("Short description", ctx.state["short"]),
                     ("SEO title", ctx.state["seo_title"]), ("Meta description", ctx.state["meta"])],
        data={"product_description": ctx.state["description"], "short_description": ctx.state["short"],
              "seo_title": ctx.state["seo_title"], "meta_description": ctx.state["meta"],
              "missing_attributes": ctx.state["missing"], "generation_modes": m})
    return f"{len(ctx.state['meta'])}/155 chars via {m['meta']}"
