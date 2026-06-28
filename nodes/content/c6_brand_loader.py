"""c6_brand_loader (L0): brand voice (model) + asset inventory (deterministic).

The permission filter on testimonials is enforced in code here AND re-enforced
at c14/c18 — an unpermissioned quote can never reach copy or schema.
"""
from __future__ import annotations

import json

from ledger import FactsLedger
from llm import call_node


def run(state: dict) -> dict:
    brand = state.get("brand_assets") or {}
    led = FactsLedger(list(state.get("facts_ledger", [])))

    usable, unusable = [], []
    for t in brand.get("testimonials", []):
        if isinstance(t, dict) and t.get("permission") is True:
            usable.append(t)
        else:
            unusable.append({"item": t, "reason": "permission missing or false"})

    hc = list(state.get("human_checkpoints", []))
    author = brand.get("author") or {}
    if not author.get("name"):
        hc.append("[HUMAN] no author in brand_assets — supply name + credentials for E-E-A-T.")

    out = call_node(
        "c6_brand_loader", "fast",
        brand_assets=json.dumps(brand),
        brand_profile=json.dumps(state.get("brand_profile") or {}),
        canonical_page_texts=json.dumps(state.get("canonical_source_texts") or {}),
        ledger_markdown=led.to_markdown(),
    )

    # human_checkpoints are typed list[str] in state. Real models sometimes
    # return structured dicts ({id, description, severity, action, issue, ...}).
    # Coerce to strings; pick a description field when present so the human
    # reader still sees what to do, else fall back to a string repr.
    def _as_str(h):
        if isinstance(h, str):
            return h.strip()
        if isinstance(h, dict):
            t = (h.get("description") or h.get("action") or h.get("issue")
                 or h.get("message") or h.get("ask") or "")
            tag = h.get("id") or h.get("category") or ""
            return (f"[HUMAN] {tag}: {t}".strip(": ") if t else f"[HUMAN] {tag or h!r}")
        return str(h)

    model_hc = [_as_str(h) for h in (out.get("human_checkpoints") or [])]
    merged_hc = hc + [h for h in model_hc if h and h not in hc]

    return {
        "brand_voice": out.get("brand_voice", {}),
        "human_checkpoints": merged_hc,
        "_c6": {"usable_testimonials": usable, "unusable_testimonials": unusable,
                "differentiators": brand.get("differentiators", [])},
        "_guardrails": [{"check": "testimonial_permissions",
                         "usable": len(usable), "excluded": len(unusable)}],
    }
