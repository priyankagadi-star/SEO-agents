"""c3_kw_intent_mapper (L0, cold mode): keyword cluster + intent from SERP data.

Deterministic, derived only from the SERP tool's output. Volumes/difficulty
are "unknown" unless real data is present — fabricated volumes are a gate
failure (BUILD-SPEC §5b).
"""
from __future__ import annotations

import re

from tools.serp import serp_search

_INTENT_RULES = [
    ("transactional", re.compile(r"\b(pricing|buy|trial|demo|signup|sign up)\b", re.I)),
    ("comparison", re.compile(r"\bvs\.?\b|\bversus\b|\balternatives?\b|\bbest\b|\btop\s+\d+\b", re.I)),
    ("informational", re.compile(r"^what|^how|^why|\bguide\b|\btutorial\b|\bdefinition\b", re.I)),
]


def run(state: dict) -> dict:
    if state["mode"] != "net_new":
        return {}
    query = state["primary_keyword"]
    res = serp_search(query)
    stub = bool(res.get("stub"))
    titles = [r.get("title", "") for r in res.get("organic", [])]
    paa = res.get("paa", [])

    cluster = [{"term": query, "volume": "unknown", "kd": "unknown", "intent": "primary"}]
    seen = {query.lower()}
    for q in paa:
        t = q.strip().rstrip("?").lower()
        if t and t not in seen:
            seen.add(t)
            cluster.append({"term": t, "volume": "unknown", "kd": "unknown", "intent": "paa"})

    basis = " ".join(titles) or query
    intent = next((name for name, pat in _INTENT_RULES if pat.search(basis)), "informational")

    return {
        "keyword_cluster": cluster,
        "intent": intent,
        "serp_analysis": {"paa": paa, "stub": stub,
                          "confidence": "stub" if stub else "live"},
        "_guardrails": [{"check": "no_fabricated_volumes",
                         "ok": all(c["volume"] == "unknown" for c in cluster) or not stub}],
    }
