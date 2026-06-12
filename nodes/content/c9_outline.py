"""c9_outline (L2): outline with an entity-coverage contract.

Emits coverage_map; unassigned entities/keep-items are reported and re-checked
deterministically at c19.
"""
from __future__ import annotations

import json

from guardrails import intent_boundary_check
from ledger import FactsLedger
from llm import call_node
from page_profiles import get_profile


def run(state: dict) -> dict:
    led = FactsLedger(list(state.get("facts_ledger", [])))
    profile = get_profile(state.get("page_type"))
    out = call_node(
        "c9_outline", "fast",
        brief=json.dumps(state.get("brief", {})),
        gap_entity_matrix=json.dumps(state.get("gap_entity_matrix", {})),
        keep_list=json.dumps(state.get("keep_list", [])),
        required_blocks=json.dumps([{"id": b.id, "intent": b.label}
                                    for b in profile.required_blocks()]),
        faq_candidates=json.dumps([]),
        ledger_markdown=led.to_markdown(),
    )
    outline = out.get("outline", out)
    unassigned = out.get("unassigned", outline.get("unassigned", []))
    # inverse coverage check: is any planned section owned by a SIBLING URL?
    trespasses = intent_boundary_check(outline, state.get("cluster_map"),
                                       state.get("page_intent"), state.get("target_url"))
    return {
        "outline": outline,
        "_guardrails": [
            {"check": "entity_coverage", "unassigned": unassigned,
             "sections": len(outline.get("sections", []))},
            {"check": "intent_boundary", "trespasses": [v.detail for v in trespasses]},
        ],
    }
