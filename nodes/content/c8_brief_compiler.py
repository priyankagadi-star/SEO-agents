"""c8_brief_compiler (L1): the working brief (structure, budgets, UI limits)."""
from __future__ import annotations

import json
from pathlib import Path

import yaml

from ledger import FactsLedger
from llm import call_node

_CFG = yaml.safe_load((Path(__file__).parents[2] / "config.yaml").read_text())


def run(state: dict) -> dict:
    led = FactsLedger(list(state.get("facts_ledger", [])))
    wb = _CFG["word_budget"].get(state.get("page_type"), [1400, 1800])
    out = call_node(
        "c8_brief_compiler", "fast",
        strategy=json.dumps(state.get("strategy", {})),
        unique_insight=state.get("unique_insight", ""),
        page_type=state.get("page_type", ""),
        word_budget=json.dumps(wb),
        ui_limits=json.dumps(_CFG["ui_limits"]),
        serp_feature_targets=json.dumps(state.get("serp_feature_targets", [])),
        gap_entity_matrix=json.dumps(state.get("gap_entity_matrix", {})),
        ledger_markdown=led.to_markdown(),
    )
    brief = out.get("brief", out)
    return {"brief": brief, "_guardrails": [{"check": "brief_compiled", "has_structure": bool(brief.get("structure"))}]}
