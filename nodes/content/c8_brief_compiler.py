"""c8_brief_compiler (L1): the working brief (structure, budgets, UI limits).

Seeds the brief from the page-type profile so every type gets its required
shape (comparison→table+verdict, glossary→definition-first, …). The model may
enrich the structure but cannot drop a required block — c8 re-merges the
profile's required blocks back in deterministically.
"""
from __future__ import annotations

import json
from pathlib import Path

import yaml

from ledger import FactsLedger
from llm import call_node
from page_profiles import get_profile

_CFG = yaml.safe_load((Path(__file__).parents[2] / "config.yaml").read_text())


def run(state: dict) -> dict:
    led = FactsLedger(list(state.get("facts_ledger", [])))
    profile = get_profile(state.get("page_type"))
    wb = profile.word_budget
    required = [{"id": b.id, "intent": b.label} for b in profile.required_blocks()]

    out = call_node(
        "c8_brief_compiler", "fast",
        strategy=json.dumps(state.get("strategy", {})),
        unique_insight=state.get("unique_insight", ""),
        page_type=state.get("page_type", ""),
        word_budget=json.dumps(wb),
        ui_limits=json.dumps(_CFG["ui_limits"]),
        serp_feature_targets=json.dumps(state.get("serp_feature_targets") or list(profile.serp_targets)),
        gap_entity_matrix=json.dumps(state.get("gap_entity_matrix", {})),
        required_blocks=json.dumps(required),
        schema_types=json.dumps(list(profile.schema_types)),
        ledger_markdown=led.to_markdown(),
    )
    brief = out.get("brief", out)

    # CONTRACT: the brief's structure must contain every required block for this
    # page type. Merge the model's structure with the profile, model order first.
    model_structure = brief.get("structure") or []
    have = {str(s.get("id") or s.get("intent", "")).lower() for s in model_structure}
    merged = list(model_structure)
    for b in profile.required_blocks():
        if b.id.lower() not in have and b.label.lower() not in have:
            merged.append({"id": b.id, "intent": b.label, "required": True})
    brief["structure"] = merged
    brief.setdefault("schema_types", list(profile.schema_types))
    brief.setdefault("word_budget", wb)
    brief["page_profile"] = profile.page_type

    return {"brief": brief,
            "_guardrails": [{"check": "brief_compiled", "page_type": profile.page_type,
                             "structure_blocks": len(merged),
                             "required_blocks": [b.id for b in profile.required_blocks()]}]}
