"""c3_kw_intent_mapper (L0, cold mode): keyword cluster + intent.

Uses real Semrush data when SEMRUSH_API_KEY is set (real volumes + difficulty —
no longer "unknown"); otherwise falls back to the SERP stub with volumes left
"unknown" (never fabricated). Intent per term from classify_intent.
"""
from __future__ import annotations

from guardrails import classify_intent
from tools.research import get_provider
from tools.serp import serp_search


def run(state: dict) -> dict:
    if state["mode"] != "net_new":
        return {}
    seed = state["primary_keyword"]
    research = get_provider().research(seed)

    cluster = [{"term": seed, "volume": "unknown", "kd": "unknown",
                "intent": classify_intent(seed), "role": "primary"}]
    seen = {seed.lower()}

    if not research.get("stub"):
        for kw in research.get("keywords", []):
            t = kw["term"].lower()
            if t == seed.lower():            # backfill the primary's real metrics
                cluster[0]["volume"] = kw["volume"]
                cluster[0]["kd"] = kw["kd"]
            elif t and t not in seen:
                seen.add(t)
                cluster.append({"term": kw["term"], "volume": kw["volume"], "kd": kw["kd"],
                                "intent": classify_intent(kw["term"]), "role": "related"})
        paa = research.get("questions", [])
        confidence = "live"
    else:
        res = serp_search(seed)
        paa = res.get("paa", [])
        for q in paa:
            t = q.strip().rstrip("?").lower()
            if t and t not in seen:
                seen.add(t)
                cluster.append({"term": t, "volume": "unknown", "kd": "unknown",
                                "intent": classify_intent(t), "role": "paa"})
        confidence = "stub" if res.get("stub") else "live"

    titles = " ".join(c["term"] for c in cluster)
    intent = classify_intent(seed) if classify_intent(seed) != "informational" else \
        (classify_intent(titles) or "informational")

    return {
        "keyword_cluster": cluster,
        "intent": intent,
        "serp_analysis": {"paa": paa, "confidence": confidence,
                          "research_source": research.get("source", "stub")},
        "_guardrails": [{"check": "keyword_research", "source": research.get("source", "stub"),
                         "terms": len(cluster), "real_volumes": not research.get("stub")}],
    }
