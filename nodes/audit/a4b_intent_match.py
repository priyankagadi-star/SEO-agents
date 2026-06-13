"""a4b_intent_match: Intent-Match Auditor (architecture v2, closes G1/G4).

Deterministic. Classifies the page's DELIVERED intent (from H1 + hero) and
compares it to the intent type its page_type should own; scores how well the
copy mirrors the page's own GSC head queries and whether each query's intent
type matches the page. Asserts only from the supplied page text + GSC rows.
"""
from __future__ import annotations

import re

from guardrails import _DEFINITIONAL, _terms, classify_intent, owned_intent_types


def run(state: dict) -> dict:
    page = state.get("page") or {}
    page_type = state.get("page_type", "feature")
    owned = owned_intent_types(page_type)

    h1 = next((t for lvl, t in page.get("headings", []) if lvl == 1), page.get("title") or "")
    text = page.get("text", "")
    lead = " ".join(text.split()[:60])

    # delivered intent: a definitional opener on a commercial page = explainer
    if owned <= {"commercial", "transactional"} and _DEFINITIONAL.search(f"{h1} {lead}".strip()):
        delivered = "informational"
    else:
        delivered = classify_intent(f"{h1} {lead}")
    intent_match = "aligned" if delivered in owned else "drifted"

    queries = (state.get("gsc") or {}).get("queries", [])
    norm = text.lower()
    coverage = []
    for q in queries:
        term = q.get("query") or q.get("term") or ""
        if not term:
            continue
        terms = _terms(term)
        mirrored = bool(terms) and sum(
            1 for w in terms if re.search(rf"\b{re.escape(w)}\b", norm)) / len(terms) >= 0.6
        qtype = classify_intent(term)
        coverage.append({"query": term, "impressions": q.get("impressions", 0),
                         "mirrored": mirrored, "intent_type": qtype,
                         "intent_match": qtype in owned,
                         "owning_page": "this" if qtype in owned else "delegate"})

    off_intent_sections = [t for lvl, t in page.get("headings", [])
                           if lvl in (2, 3) and classify_intent(t) not in owned]

    commercial = [c for c in coverage if c["intent_match"]]
    mirrored_share = (sum(1 for c in commercial if c["mirrored"]) / len(commercial)
                      if commercial else None)
    if intent_match == "drifted":
        score = 0
    elif mirrored_share is not None and mirrored_share < 0.6:
        score = 1
    else:
        score = 2

    return {"intent_findings": {
        "delivered_intent": delivered,
        "expected_intent": next(iter(owned)) if len(owned) == 1 else "commercial",
        "intent_match": intent_match,
        "drift_reason": (f"page delivers '{delivered}' but {page_type} pages own {sorted(owned)}"
                         if intent_match == "drifted" else ""),
        "head_query_coverage": coverage,
        "offintent_sections": off_intent_sections,
        "mirrored_share": mirrored_share,
        "score_0_2": score,
        "verdict": intent_match,
    }}
