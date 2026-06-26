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

    # Structural flexibility: the template is the FLOOR, not the ceiling.
    # Surface candidate ADDITIONS from research so the strategist can extend
    # the structure when competitor coverage or current trends call for it.
    gap = state.get("gap_entity_matrix") or {}
    template_blob = " ".join(b.label.lower() + " " + b.id.lower() for b in profile.required_blocks())
    candidate_additions = [
        s for s in (gap.get("missing_subtopics") or [])
        if isinstance(s, str) and not any(w in template_blob for w in s.lower().split()[:2])
    ][:8]
    # owner-supplied "what's happening now" — brand_profile or inputs.json
    rd = state.get("research_dossier") or {}
    trend_signals = (state.get("brand_profile") or {}).get("trend_signals") or \
                    rd.get("trend_signals") or []
    # research for information gain: real market stats, authoritative external
    # sources, real PAA questions. Surfaced so the brief carries a market-context
    # section + a sources block the writer can cite (raises the GOAL score).
    market_stats = rd.get("market_stats") or []
    external_sources = rd.get("external_sources") or []
    real_questions = rd.get("real_questions") or []

    out = call_node(
        "c8_brief_compiler", "strong",
        strategy=json.dumps(state.get("strategy", {})),
        unique_insight=state.get("unique_insight", ""),
        page_type=state.get("page_type", ""),
        word_budget=json.dumps(wb),
        ui_limits=json.dumps(_CFG["ui_limits"]),
        serp_feature_targets=json.dumps(state.get("serp_feature_targets") or list(profile.serp_targets)),
        gap_entity_matrix=json.dumps(state.get("gap_entity_matrix", {})),
        required_blocks=json.dumps(required),
        candidate_additions=json.dumps(candidate_additions),
        trend_signals=json.dumps(trend_signals),
        market_stats=json.dumps(market_stats),
        external_sources=json.dumps(external_sources),
        real_questions=json.dumps(real_questions),
        schema_types=json.dumps(list(profile.schema_types)),
        ledger_markdown=led.to_markdown(),
    )
    brief = out.get("brief", out)
    if not isinstance(brief, dict):   # real models sometimes return a list/string
        brief = {"structure": brief if isinstance(brief, list) else []}

    # CONTRACT: the brief's structure must contain every required block for this
    # page type. Merge the model's structure with the profile, model order first.
    # structure items may come back as strings or dicts — normalize to dicts
    raw_structure = brief.get("structure") or []
    if not isinstance(raw_structure, list):
        raw_structure = []
    model_structure = [{"intent": s} if isinstance(s, str) else s
                       for s in raw_structure if isinstance(s, (str, dict))]
    have = {str(s.get("id") or s.get("intent", "")).lower() for s in model_structure}
    merged = list(model_structure)
    for b in profile.required_blocks():
        if b.id.lower() not in have and b.label.lower() not in have:
            merged.append({"id": b.id, "intent": b.label, "required": True})
    # research-driven additions: a market-context section (cite real stats +
    # external sources) goes near the top; carry sources + real PAA on the brief
    # so c9 (outline), c11 (drafter) and c12 (faq) can use them.
    if market_stats or external_sources:
        have_ids = {str(s.get("id") or s.get("intent", "")).lower() for s in merged}
        if "market_context" not in have_ids:
            insert_at = 1 if merged else 0
            merged.insert(insert_at, {
                "id": "market_context",
                "intent": "Why this matters now — cite real market stats and external authoritative sources",
                "cite_facts": [f"mkt-*"] if market_stats else [],
                "from_research": True})
    brief["structure"] = merged
    brief.setdefault("schema_types", list(profile.schema_types))
    brief.setdefault("word_budget", wb)
    if market_stats:
        brief["market_stats"] = market_stats
    if external_sources:
        brief["external_sources"] = external_sources
    if real_questions:
        brief["real_questions"] = real_questions
    brief["page_profile"] = profile.page_type

    return {"brief": brief,
            "_guardrails": [{"check": "brief_compiled", "page_type": profile.page_type,
                             "structure_blocks": len(merged),
                             "research_seeded": bool(market_stats or external_sources),
                             "required_blocks": [b.id for b in profile.required_blocks()]}]}
