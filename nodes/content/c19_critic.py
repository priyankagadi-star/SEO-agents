"""c19_critic (L6): adversarial critic, deterministic-first.

Runs fact_diff / quantifier_check / flag_dont_fill on the merged draft, checks
keep_list survival and unresolved [VERIFY], and names the owning step for each
failure. Any blocker ⇒ verdict "fail" (which routes back to the owning layer).
LLM-assisted nuance checks are layered on in later phases; the deterministic
guardrails are authoritative — they are the product.
"""
from __future__ import annotations

import re
from pathlib import Path

import yaml

from guardrails import (
    VERIFY_PAT,
    ai_tell_check,
    anaphora_check,
    fact_diff,
    flag_dont_fill,
    information_gain_score,
    intent_boundary_check,
    intent_fit_check,
    quantifier_check,
    vague_comparative_check,
)
from ledger import FactsLedger
from llm import client_is_scripted

_CFG = yaml.safe_load((Path(__file__).parents[2] / "config.yaml").read_text())
_GOAL = _CFG.get("goal", {}) or {}


def run(state: dict) -> dict:
    led = FactsLedger(list(state.get("facts_ledger", [])))
    draft = state.get("draft", "")
    failures: list[dict] = []

    for v in fact_diff(draft, led):
        failures.append({"description": v.detail, "owning_step": "c11_section_drafter",
                         "severity": "blocker", "evidence": v.detail,
                         "fix": "Correct the contradicted value to match the locked ledger fact."})
    for v in flag_dont_fill(draft, led):
        failures.append({"description": v.detail, "owning_step": "c11_section_drafter",
                         "severity": "blocker", "evidence": v.detail,
                         "fix": "Cite a (fact:id) or mark the number as [VERIFY: …]."})
    for v in quantifier_check(draft, led):
        failures.append({"description": v.detail, "owning_step": "c11_section_drafter",
                         "severity": v.severity, "evidence": v.detail,
                         "fix": "Ground the quantifier in a verified fact or soften it."})

    # keep_list survival (dropping a kept strength is the classic rebuild failure).
    # Entity-like keeps (proper-noun items, e.g. "Sample Variance differentiator")
    # are deterministically checkable by substring -> blocker when absent.
    # Quality-phrase keeps from the audit (all-lowercase, e.g. "single clear H1")
    # can't be substring-matched in prose -> surfaced as major for c21, the
    # comparison judge, which verifies them against the live page.
    for item in state.get("keep_list") or []:
        s = str(item)
        token = s.split(" differentiator")[0].strip()
        if token and token.lower() not in draft.lower():
            # proper-noun word ("Sample") => entity; acronyms ("H1","FAQ","AI") don't count
            entity_like = bool(re.search(r"\b[A-Z][a-z]+", s))
            failures.append({"description": f"keep_list item missing from draft: {item}",
                             "owning_step": "c9_outline",
                             "severity": "blocker" if entity_like else "major",
                             "evidence": item,
                             "fix": "Assign this kept strength to a section and cover it."})

    # entity coverage from the gap matrix (reported as major in Phase 1)
    gap = state.get("gap_entity_matrix") or {}
    for entity in gap.get("missing_entities", []):
        if str(entity).lower() not in draft.lower():
            failures.append({"description": f"gap entity not covered: {entity}",
                             "owning_step": "c9_outline", "severity": "major", "evidence": entity,
                             "fix": "Add a section/passage covering this entity."})

    # intent boundary: a drafted section owned by a sibling URL is a blocker —
    # the cluster-level sibling of fact_diff (host→link). Single-page mode is a no-op.
    for v in intent_boundary_check(state.get("outline") or {}, state.get("cluster_map"),
                                   state.get("page_intent"), state.get("target_url")):
        failures.append({"description": v.detail, "owning_step": "c9_outline",
                         "severity": "blocker", "evidence": v.detail,
                         "fix": "Convert this section to an internal link to the owning URL; do not host it."})

    # Intent-Fit gate (v2): delivered intent, H1 keyword, query mirroring,
    # delegated links. Active only for a governed contract (cluster_map/GSC).
    _IFIT_OWNER = {"h1_missing_keyword": "c8_brief_compiler",
                   "intent_drift": "c10_hook", "low_mirror_score": "c11_section_drafter",
                   "missing_delegated_link": "c9_outline"}
    contract = state.get("intent_contract") or {}
    h1 = (state.get("brief") or {}).get("title_direction")
    for v in intent_fit_check(draft, contract, h1=h1):
        failures.append({"description": v.detail,
                         "owning_step": _IFIT_OWNER.get(v.kind, "c11_section_drafter"),
                         "severity": v.severity, "evidence": v.detail,
                         "fix": "Re-align the page to its commercial intent and buyer vocabulary."})

    # Content-quality gates: AI-tells, anaphora, vague comparisons
    # (closes the AI-smell gap surfaced in live Siftly runs)
    for v in ai_tell_check(draft):
        failures.append({"description": v.detail, "owning_step": "c11_section_drafter",
                         "severity": v.severity, "evidence": v.detail,
                         "fix": "Rewrite without AI-tell phrases ('fundamentally', 'reshaping', 'leverages', etc.)."})
    for v in anaphora_check(draft):
        failures.append({"description": v.detail, "owning_step": "c11_section_drafter",
                         "severity": v.severity, "evidence": v.detail,
                         "fix": "Vary sentence openers; do not start ≥4 sentences with the same word/bigram."})
    for v in vague_comparative_check(draft):
        failures.append({"description": v.detail, "owning_step": "c7_strategist",
                         "severity": v.severity, "evidence": v.detail,
                         "fix": "Name the competitor or cite a verified fact; no 'most tools' / 'unlike others' filler."})

    # unresolved evidence flags must not ship
    for flag in VERIFY_PAT.findall(draft):
        failures.append({"description": f"unresolved evidence flag in draft: {flag}",
                         "owning_step": "c13_evidence", "severity": "blocker", "evidence": flag,
                         "fix": "Resolve or cut the flagged claim before publishing."})

    # GOAL gate: Information-Gain Score. Form-clean pages can still be thin —
    # this fails any page that scores < pass_score or misses a hard pre-condition
    # (value density, sourced freshness, unresolved [VERIFY]). enforce flag in
    # config decides whether the gate blocks (route-back) or is advisory-only.
    enforce = bool(_GOAL.get("enforce_information_gain", False)) and not client_is_scripted()
    pass_score = float(_GOAL.get("pass_score", 70))
    brand_profile = state.get("brand_profile") or {}
    brand_name = brand_profile.get("name") or "Siftly"
    trends = (brand_profile.get("trend_signals")
              or (state.get("research_dossier") or {}).get("trend_signals") or [])
    owner_domains = []
    for u in (state.get("canonical_sources") or []) + [state.get("target_url") or ""]:
        m = re.search(r"https?://([a-z0-9.\-]+)", str(u), re.I)
        if m:
            owner_domains.append(m.group(1))
    goal = information_gain_score(
        draft, led,
        author=(state.get("brand_assets") or {}).get("author"),
        serp_entities=(state.get("serp_analysis") or {}).get("entities")
        or (gap.get("entity_set") if isinstance(gap, dict) else None),
        paa_questions=(state.get("serp_analysis") or {}).get("paa")
        or (state.get("serp_analysis") or {}).get("questions"),
        faq=state.get("faq"),
        trend_signals=trends,
        brand_names=[brand_name],
        owner_domains=owner_domains,
        word_budget=(state.get("brief") or {}).get("word_budget"),
        threshold=pass_score,
        enforce=enforce,
    )
    _GOAL_OWNER = {
        "goal_information_gain": "c7_strategist",
        "goal_precondition:distinct_value_density": "c11_section_drafter",
        "goal_precondition:freshness_sourced_trend": "c8_brief_compiler",
        "goal_precondition:no_unresolved_verify": "c13_evidence",
    }
    for v in goal.violations:
        failures.append({"description": v.detail,
                         "owning_step": _GOAL_OWNER.get(v.kind, "c7_strategist"),
                         "severity": v.severity, "evidence": v.kind,
                         "fix": "Add external citations, sourced data points, and concrete "
                                "examples; cut padding and self-promotion to raise the score."})

    blockers = [f for f in failures if f["severity"] == "blocker"]
    verdict = "fail" if blockers else "pass"
    return {
        "critic_report": {"verdict": verdict, "failures": failures, "blocker_count": len(blockers),
                          "information_gain": {"score": goal.score, "passed": goal.passed,
                                               "threshold": goal.threshold,
                                               "metrics": goal.metrics,
                                               "preconditions": goal.preconditions}},
        "_guardrails": [{"check": "critic", "verdict": verdict, "failures": len(failures),
                         "information_gain_score": goal.score}],
    }
