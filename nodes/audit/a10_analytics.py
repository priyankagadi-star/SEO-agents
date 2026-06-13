"""a10_analytics: GSC analysis incl. the AIO zero-click rule (BUILD-SPEC §5a).
Deterministic — all math done by tools/gsc; this node interprets honestly."""
from __future__ import annotations

AIO_FLAG = ("likely AI-Overview citations — CTR is structurally suppressed; "
            "judge on AI-citation share instead")


def run(state: dict) -> dict:
    gsc = state.get("gsc") or {}
    if not gsc or not gsc.get("queries"):
        return {"performance": {"status": "no-gsc-data",
                                "note": "no GSC export supplied; performance not assessed"}}

    totals = gsc["totals"]
    anomalies = gsc.get("zero_click_anomalies", [])
    perf = {
        "impressions": totals["impressions"],
        "clicks": totals["clicks"],
        "ctr": round(totals["ctr"], 4),
        "expected_clicks": totals["expected_clicks"],
        "striking_distance_queries": [q["query"] for q in gsc.get("striking_distance_queries", [])[:10]],
        "aio_zero_click_share": gsc.get("zero_click_anomaly_score", 0.0),
    }
    if anomalies:
        perf["aio_flag"] = AIO_FLAG
        perf["aio_affected_queries"] = [q["query"] for q in anomalies[:10]]

    # intent-type mix + commercial striking distance (pos 5-20, <=1 click)
    from guardrails import classify_intent
    mix: dict[str, int] = {}
    commercial_striking = []
    for q in gsc["queries"]:
        it = classify_intent(q.get("query", ""))
        mix[it] = mix.get(it, 0) + 1
        if 5 <= q.get("position", 0) <= 20 and q.get("clicks", 0) <= 1 and it in ("commercial", "transactional"):
            commercial_striking.append(q.get("query"))
    total = sum(mix.values()) or 1
    perf["intent_type_mix"] = {k: round(v / total, 3) for k, v in mix.items()}
    perf["commercial_striking_distance"] = commercial_striking[:10]
    perf["language_note"] = ("GSC query export carries no per-query language; "
                             "hreflang demand needs the Countries.csv / a language signal")
    return {"performance": perf}
