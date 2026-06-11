"""c12_faq (L3): PAA-sourced FAQ, deduped vs body, no new stats."""
from __future__ import annotations

import json

from ledger import FactsLedger
from llm import call_node


def run(state: dict) -> dict:
    led = FactsLedger(list(state.get("facts_ledger", [])))
    outline_summary = [s.get("h2") for s in (state.get("outline") or {}).get("sections", [])]
    out = call_node(
        "c12_faq", "fast",
        paa_questions=json.dumps(state.get("serp_analysis", {}).get("paa", []) if isinstance(state.get("serp_analysis"), dict) else []),
        outline_summary=json.dumps(outline_summary),
        primary_keyword=state["primary_keyword"],
        ledger_markdown=led.to_markdown(),
    )
    faq = out.get("faq", [])
    return {"faq": faq, "_guardrails": [{"check": "faq", "count": len(faq)}]}
