"""c4_serp_landscape (L0, cold mode): dominant format + serp_feature_targets.

Deterministic over the SERP tool output; stubbed data is labeled, never embellished.
"""
from __future__ import annotations

import re

from tools.serp import serp_search

_FORMAT_RULES = [
    ("blog-listicle", re.compile(r"\btop\s+\d+|\b\d+\s+(best|tools|ways|tips)\b|\bbest\b", re.I)),
    ("comparison", re.compile(r"\bvs\.?\b|\bversus\b|\balternatives?\b", re.I)),
    ("guide", re.compile(r"\bguide\b|\bhow to\b|\btutorial\b", re.I)),
    ("glossary", re.compile(r"^what is\b|\bdefinition\b", re.I)),
]


def run(state: dict) -> dict:
    if state["mode"] != "net_new":
        return {}
    res = serp_search(state["primary_keyword"])
    stub = bool(res.get("stub"))
    titles = [r.get("title", "") for r in res.get("organic", [])]

    votes: dict[str, int] = {}
    for t in titles:
        for fmt, pat in _FORMAT_RULES:
            if pat.search(t):
                votes[fmt] = votes.get(fmt, 0) + 1
                break
    dominant = max(votes, key=votes.get) if votes else state.get("page_type", "feature")

    targets = []
    if res.get("paa"):
        targets.append("people_also_ask")
    if titles:
        targets.append("featured_snippet")
    targets.append("aio_citation")  # the platform's raison d'être — always a target

    return {
        "serp_feature_targets": targets,
        "serp_analysis": {**(state.get("serp_analysis") or {}),
                          "dominant_format": dominant,
                          "format_votes": votes,
                          "confidence": "stub" if stub else "live"},
    }
