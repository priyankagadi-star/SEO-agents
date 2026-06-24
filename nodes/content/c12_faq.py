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
    # normalize to [{"q","a"}] — models return dicts (q/a, question/answer),
    # {question: answer} maps, or bare strings.
    raw = out.get("faq") or out.get("faqs") or []
    if isinstance(raw, dict):
        raw = [{"q": k, "a": v} for k, v in raw.items()]
    faq = []
    for item in raw if isinstance(raw, list) else []:
        if isinstance(item, dict):
            q = item.get("q") or item.get("question") or item.get("name") or ""
            a = item.get("a") or item.get("answer") or item.get("acceptedAnswer") or ""
            if isinstance(a, dict):
                a = a.get("text", "")
            if q:
                faq.append({"q": str(q), "a": str(a)})
        elif isinstance(item, str):
            faq.append({"q": item, "a": ""})
    return {"faq": faq, "_guardrails": [{"check": "faq", "count": len(faq)}]}
