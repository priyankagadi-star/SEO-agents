"""c10_hook (L3): answer-first lead, 40-60 words."""
from __future__ import annotations

import json

from guardrails import flag_dont_fill
from ledger import FactsLedger
from llm import call_node


def run(state: dict) -> dict:
    led = FactsLedger(list(state.get("facts_ledger", [])))
    out = call_node(
        "c10_hook", "fast",
        primary_keyword=state["primary_keyword"],
        unique_insight=state.get("unique_insight", ""),
        audience=state.get("audience", ""),
        brand_voice=json.dumps(state.get("brand_voice", {})),
        ledger_markdown=led.to_markdown(),
    )
    lead = out.get("lead", "")
    violations = flag_dont_fill(lead, led)
    return {
        "lead": lead,
        "_guardrails": [{"check": "answer_first", "words": len(lead.split()),
                         "flag_dont_fill": [v.detail for v in violations]}],
    }
