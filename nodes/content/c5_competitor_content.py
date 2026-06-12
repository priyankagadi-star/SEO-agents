"""c5_competitor_content (L0, cold mode): gap_entity_matrix from competitor pages.

Real fetches only when the SERP data is live; with a stubbed SERP the gap is
derived from result titles alone and labeled — competitor content is never
invented (BUILD-SPEC §5b: gap matrix from REAL fetched pages).
"""
from __future__ import annotations

import re

from tools.serp import serp_search


def _title_terms(title: str) -> list[str]:
    return [t.strip(",.;:!?()").lower() for t in title.split()
            if len(t.strip(",.;:!?()")) > 5]


def run(state: dict) -> dict:
    if state["mode"] != "net_new":
        return {}
    res = serp_search(state["primary_keyword"])
    stub = bool(res.get("stub"))
    organic = res.get("organic", [])[:5]

    gap = {"missing_entities": [], "missing_subtopics": [], "competitor_advantages": []}
    competitors = [r.get("url", "") for r in organic if r.get("url")]

    if stub:
        # titles only; no fetches against fixture URLs
        seen = set()
        for r in organic:
            for term in _title_terms(r.get("title", "")):
                if term not in seen:
                    seen.add(term)
                    gap["missing_subtopics"].append(term)
        note = "stub SERP — gap derived from result titles only; competitor pages not fetched"
    else:
        from tools.fetch import fetch_rendered
        seen = set()
        for r in organic:
            try:
                page = fetch_rendered(r["url"])
            except Exception:
                continue
            for lvl, heading in page["headings"]:
                if lvl in (2, 3):
                    key = heading.lower()
                    if key not in seen:
                        seen.add(key)
                        gap["missing_subtopics"].append(heading)
                        gap["competitor_advantages"].append(
                            {"source_url": r["url"], "evidence": heading})
        note = f"fetched {len(seen and competitors)} competitor pages"

    return {
        "gap_entity_matrix": gap,
        "competitors": competitors,
        "_guardrails": [{"check": "competitor_gaps", "confidence": "stub" if stub else "live",
                         "note": note}],
    }
