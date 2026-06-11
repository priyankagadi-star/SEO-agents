"""c7_strategist (L1): unique_insight + strategy + keep_plan.

grounding_check runs at exit; violations are reported here and enforced as
gate failures at c19 (writer ≠ verifier).
"""
from __future__ import annotations

import json

from guardrails import grounding_check
from ledger import FactsLedger
from llm import call_node


def run(state: dict) -> dict:
    led = FactsLedger(list(state.get("facts_ledger", [])))
    out = call_node(
        "c7_strategist", "strong",
        mode=state["mode"],
        primary_keyword=state["primary_keyword"],
        audience=state.get("audience", ""),
        gap_entity_matrix=json.dumps(state.get("gap_entity_matrix", {})),
        keep_list=json.dumps(state.get("keep_list", [])),
        failure_modes=json.dumps(state.get("failure_modes", [])),
        usable_assets=json.dumps(state.get("brand_assets", {})),
        research_dossier=json.dumps(state.get("research_dossier", {})),
        ledger_markdown=led.to_markdown(),
    )
    claims = list(out.get("claims", []))
    if out.get("unique_insight"):
        claims.append(out["unique_insight"])
    violations = grounding_check(claims, led)
    return {
        "unique_insight": out.get("unique_insight", ""),
        "strategy": out.get("strategy", {}),
        "_c7": out,
        "_guardrails": [{"check": "grounding_check", "violations": [v.detail for v in violations]}],
    }
