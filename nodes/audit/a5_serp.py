"""a5_serp: top-10 read via tools/serp. A stubbed tool yields
confidence:"stub" and an empty gap matrix — never fabricated competitors."""
from __future__ import annotations

from tools.serp import serp_search


def run(state: dict) -> dict:
    query = state.get("primary_query", "")
    res = serp_search(query)
    stub = bool(res.get("stub"))
    organic = res.get("organic", [])

    gap = {"missing_entities": [], "missing_subtopics": [], "competitor_advantages": []}
    our_text = state["page"]["text"].lower()
    for r in organic[:10]:
        for token in (r.get("title") or "").split():
            t = token.strip(",.;:!?()").lower()
            if len(t) > 5 and t not in our_text and t not in gap["missing_subtopics"]:
                gap["missing_subtopics"].append(t)

    return {
        "serp_findings": {
            "confidence": "stub" if stub else "live",
            "result_count": len(organic),
            "paa": res.get("paa", []),
            "note": res.get("note", ""),
            "score_0_2": None if stub else 1,
        },
        "gap_entity_matrix": gap,
    }
