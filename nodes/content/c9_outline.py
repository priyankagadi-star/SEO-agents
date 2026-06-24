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
    # normalize real-model shape variation: outline may come back as a dict,
    # a bare list of sections, or with sections under "structure"; sections may
    # be strings or dicts missing id/h2.
    outline = out.get("outline", out)
    if isinstance(outline, list):
        outline = {"sections": outline}
    if not isinstance(outline, dict):
        outline = {"sections": []}
    raw_sections = outline.get("sections") or outline.get("structure") or []
    if isinstance(raw_sections, dict):
        raw_sections = list(raw_sections.values())
    norm = []
    for i, s in enumerate(raw_sections if isinstance(raw_sections, list) else []):
        if isinstance(s, str):
            s = {"h2": s}
        if not isinstance(s, dict):
            continue
        s["id"] = s.get("id") or f"s{i + 1}"
        s["h2"] = s.get("h2") or s.get("title") or s.get("heading") or s.get("intent") or f"Section {i + 1}"
        norm.append(s)
    outline["sections"] = norm
    unassigned = out.get("unassigned") or (outline.get("unassigned") if isinstance(outline.get("unassigned"), list) else []) or []
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
