"""c9_outline (L2): outline with an entity-coverage contract.

Emits coverage_map; unassigned entities/keep-items are reported and re-checked
deterministically at c19.
"""
from __future__ import annotations

import json

from ledger import FactsLedger
from llm import call_node


def run(state: dict) -> dict:
    led = FactsLedger(list(state.get("facts_ledger", [])))
    out = call_node(
        "c9_outline", "fast",
        brief=json.dumps(state.get("brief", {})),
        gap_entity_matrix=json.dumps(state.get("gap_entity_matrix", {})),
        keep_list=json.dumps(state.get("keep_list", [])),
        faq_candidates=json.dumps([]),
        ledger_markdown=led.to_markdown(),
    )
    outline = out.get("outline", out)
    unassigned = out.get("unassigned", outline.get("unassigned", []))
    return {
        "outline": outline,
        "_guardrails": [{"check": "entity_coverage", "unassigned": unassigned,
                         "sections": len(outline.get("sections", []))}],
    }
