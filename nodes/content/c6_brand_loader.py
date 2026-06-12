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
        canonical_page_texts=json.dumps(state.get("canonical_source_texts") or {}),
        ledger_markdown=led.to_markdown(),
    )

    return {
        "brand_voice": out.get("brand_voice", {}),
        "human_checkpoints": hc + [h for h in out.get("human_checkpoints", []) if h not in hc],
        "_c6": {"usable_testimonials": usable, "unusable_testimonials": unusable,
                "differentiators": brand.get("differentiators", [])},
        "_guardrails": [{"check": "testimonial_permissions",
                         "usable": len(usable), "excluded": len(unusable)}],
    }
