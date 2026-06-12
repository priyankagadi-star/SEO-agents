"""c2_cannibalization (L0): flag sitemap URLs overlapping the primary keyword.

Deterministic. Only fetches when an account-configured sitemap URL exists;
otherwise reports "not-checked" honestly (never guesses overlap).
"""
from __future__ import annotations

import re
from urllib.parse import urlparse


def _slug_terms(url: str) -> set[str]:
    path = urlparse(url).path
    return {t for t in re.split(r"[/\-_.]+", path.lower()) if len(t) > 2}


def run(state: dict) -> dict:
    sitemap_url = state.get("sitemap")
    if not sitemap_url:
        return {"_guardrails": [{"check": "cannibalization", "status": "not-checked",
                                 "note": "no sitemap configured for this account"}]}

    import httpx
    try:
        resp = httpx.get(sitemap_url, timeout=20.0, follow_redirects=True)
        urls = re.findall(r"<loc>\s*([^<\s]+)\s*</loc>", resp.text)
    except Exception as e:  # degrade honestly, do not fail the run on a sitemap hiccup
        return {"_guardrails": [{"check": "cannibalization", "status": "not-checked",
                                 "note": f"sitemap fetch failed: {e}"}]}

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
        "competitors": state.get("competitors", []),
        "_guardrails": [{"check": "cannibalization", "status": "checked",
                         "overlapping": overlapping,
                         "risk": "high" if len(overlapping) > 2 else
                                 ("medium" if overlapping else "low")}],
    }
