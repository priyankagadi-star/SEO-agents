"""c1_source_reconciler (L0): seed the Facts Ledger from diagnosis + canonical.

The model proposes candidate facts (faithful extraction); the deterministic
canonical_verify makes the final verified/unverified/conflict call when source
texts are available. Conflicting re-adds surface via FactsLedger, never overwrite.
"""
from __future__ import annotations

import json

from guardrails import canonical_verify
from ledger import FactsLedger
from llm import call_node

_ALLOWED = {"id", "claim", "value", "source_url", "verified_by", "status", "conflict_values", "claim_pattern"}
_VERDICT_MAP = {"verified": "verified", "conflict": "conflict", "unverified": "VERIFY"}


def run(state: dict) -> dict:
    led = FactsLedger(list(state.get("facts_ledger", [])))
    # seed owner-asserted brand facts as verified (so writers can cite them
    # instead of flagging [VERIFY] for everything the brand already documents)
    from brand_facts import facts_from_brand
    for f in facts_from_brand(state.get("brand_profile") or {}, state.get("brand_assets") or {}):
        led.add(f)
    rd = state.get("research_dossier") or {}
    claims = list(state.get("failure_modes") or [])
    claims += [str(x) for x in (state.get("keep_list") or [])]
    if isinstance(rd, dict):
        claims += list(rd.get("claims", []))
    canonical_texts = state.get("canonical_source_texts") or {}

    out = call_node(
        "c1_source_reconciler", "strong",
        diagnosis_claims=json.dumps(claims),
        canonical_source_texts=json.dumps(canonical_texts),
        source_precedence=json.dumps(state.get("source_precedence", [])),
        ledger_markdown=led.to_markdown(),
    )

    conflicts = list(state.get("conflicts", []))
    for pf in out.get("proposed_facts", []):
        if "id" not in pf or "value" not in pf:
            continue
        status = pf.get("status", "VERIFY")
        if canonical_texts:
            status = _VERDICT_MAP[canonical_verify(pf["value"], canonical_texts)]
        fact = {k: pf[k] for k in pf if k in _ALLOWED}
        fact.update({
            "id": pf["id"], "claim": pf.get("claim", pf["id"]), "value": pf["value"],
            "source_url": pf.get("source_url", ""), "verified_by": "c1_source_reconciler",
            "status": status,
        })
        added = led.add(fact)
        if added["status"] == "conflict" and not any(c.get("fact_id") == added["id"] for c in conflicts):
            conflicts.append({"fact_id": added["id"], "values": added.get("conflict_values", [])})

    return {
        "facts_ledger": led.facts,
        "conflicts": conflicts,
        "_guardrails": [{"check": "seed_ledger", "facts": len(led), "conflicts": len(conflicts)}],
    }
