"""c2_cannibalization (L0) — Cannibalization & Intent Guard.

Two deterministic jobs at creation time, before any section is drafted:
1. Sitemap overlap: flag existing URLs that already target the primary keyword
   (honest "not-checked" without a configured sitemap).
2. Intent guard (the L−1 contract): using the site cluster_map, resolve THIS
   page's owned intent (page_intent) and, for each planned subtopic, decide
   host vs link. Subtopics a sibling URL owns become a linking requirement
   (delegate_list), not a section. Without a cluster_map this is single-page
   mode — page_intent = primary keyword, nothing delegated.
"""
from __future__ import annotations

import re
from urllib.parse import urlparse

from cluster_map import ClusterMap


def _slug_terms(url: str) -> set[str]:
    path = urlparse(url).path
    return {t for t in re.split(r"[/\-_.]+", path.lower()) if len(t) > 2}


def _intent_guard(state: dict) -> dict:
    cm = ClusterMap.from_config(state.get("cluster_map"))
    if cm is None:
        # single-page mode: no site topology, optimize in isolation
        return {"page_intent": state["primary_keyword"], "delegate_list": [],
                "_intent": {"mode": "single-page", "host_vs_link": []}}

    target = state.get("target_url", "")
    own = cm.match(target) or cm.match(state["primary_keyword"])
    page_intent = own.intent if own else state["primary_keyword"]
    cur = target.rstrip("/")

    gap = state.get("gap_entity_matrix") or {}
    planned = list(gap.get("missing_subtopics", [])) + list(gap.get("missing_entities", []))
    host_vs_link, delegate_list = [], []
    for sub in planned:
        m = cm.match(str(sub))
        trespass = (m is not None and m.intent != page_intent
                    and not (cur and m.url.rstrip("/") == cur))
        if trespass:
            host_vs_link.append({"subtopic": sub, "verdict": "link",
                                 "link_to": m.url, "owner_intent": m.intent})
            if m.intent not in delegate_list:
                delegate_list.append(m.intent)
        else:
            host_vs_link.append({"subtopic": sub, "verdict": "host"})
    return {"page_intent": page_intent, "delegate_list": delegate_list,
            "_intent": {"mode": "cluster", "host_vs_link": host_vs_link}}


def _build_contract(state: dict, guard: dict) -> dict:
    from intent import build_intent_contract
    from page_profiles import get_profile
    profile = get_profile(state.get("page_type"))
    head_queries = state.get("head_queries") or (state.get("gsc") or {}).get("queries") or []
    contract = build_intent_contract(
        page_type=state.get("page_type", "feature"),
        primary_keyword=state["primary_keyword"],
        cluster_map=state.get("cluster_map"),
        target_url=state.get("target_url", ""),
        head_queries=head_queries,
        required_template_sections=[b.label for b in profile.required_blocks()],
    )
    # canonical delegate_list = cluster siblings ∪ subtopic-level delegations
    delegated = sorted(set(contract["delegated_query_classes"]) | set(guard["delegate_list"]))
    return contract, delegated


def run(state: dict) -> dict:
    guard = _intent_guard(state)
    contract, delegate_list = _build_contract(state, guard)
    page_intent = contract["page_intent"]
    intent_gr = {"check": "intent_guard", "mode": guard["_intent"]["mode"],
                 "governed": contract["governed"],
                 "page_intent": page_intent,
                 "primary_intent_type": contract["primary_intent_type"],
                 "delegate": delegate_list,
                 "head_queries": len(contract["head_queries"]),
                 "host_vs_link": guard["_intent"]["host_vs_link"]}
    owned = {"intent_contract": contract, "page_intent": page_intent,
             "delegate_list": delegate_list}

    sitemap_url = state.get("sitemap")
    if not sitemap_url:
        return {**owned,
                "_guardrails": [{"check": "cannibalization", "status": "not-checked",
                                 "note": "no sitemap configured for this account"}, intent_gr]}

    import httpx
    try:
        transport = httpx.HTTPTransport(retries=2)
        with httpx.Client(timeout=20.0, transport=transport, follow_redirects=True) as client:
            resp = client.get(sitemap_url)
        urls = re.findall(r"<loc>\s*([^<\s]+)\s*</loc>", resp.text)
    except Exception as e:  # degrade honestly, never fail the run on a sitemap hiccup
        return {**owned,
                "_guardrails": [{"check": "cannibalization", "status": "not-checked",
                                 "note": f"sitemap fetch failed: {e}"}, intent_gr]}

    kw_terms = {t for t in state["primary_keyword"].lower().split() if len(t) > 2}
    target = (state.get("target_url") or "").rstrip("/")
    overlapping = []
    for u in urls:
        if u.rstrip("/") == target:
            continue
        shared = kw_terms & _slug_terms(u)
        if len(shared) >= max(2, len(kw_terms) - 1):
            overlapping.append({"url": u, "overlap_reason": f"slug shares terms {sorted(shared)}",
                                "recommendation": "differentiate"})
    return {
        **owned,
        "_guardrails": [{"check": "cannibalization", "status": "checked",
                         "overlapping": overlapping,
                         "risk": "high" if len(overlapping) > 2 else
                                 ("medium" if overlapping else "low")}, intent_gr],
    }
