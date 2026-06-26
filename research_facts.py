"""Seed the Facts Ledger from research-dossier data (architecture: c1).

Cold-mode research (Semrush volumes, the live SERP's authoritative sources,
real People-Also-Ask questions) is the raw material for *information gain* —
the thing the GOAL gate scores. Turning it into verified ledger facts lets the
writer cite external corroboration and real market data with (fact:id) refs,
instead of leaning only on owner claims. Deterministic, no model calls.

market_stats  -> verified facts (source = provider, e.g. Semrush)  -> sourced data points
external_sources -> verified citation facts (source = the real URL) -> external authoritative citations
"""
from __future__ import annotations

import re


def _slug(s: str) -> str:
    return re.sub(r"[^a-z0-9]+", "-", str(s).lower()).strip("-")[:40] or "src"


def facts_from_research(research_dossier: dict) -> list[dict]:
    """Convert dossier research into verified ledger facts the writer can cite."""
    rd = research_dossier or {}
    facts: list[dict] = []
    seen: set[str] = set()

    def add(fid: str, claim: str, value: str, source: str, verified_by: str):
        if not value or not str(value).strip():
            return
        base, i = fid, 1
        while fid in seen:
            i += 1
            fid = f"{base}-{i}"
        seen.add(fid)
        facts.append({"id": fid, "claim": claim, "value": str(value),
                      "source_url": source, "verified_by": verified_by, "status": "verified"})

    # market statistics (real search demand etc.) — each a sourced data point
    for i, ms in enumerate(rd.get("market_stats") or [], 1):
        if isinstance(ms, dict):
            stat, src = ms.get("stat") or ms.get("value"), ms.get("source") or "research"
        else:
            stat, src = str(ms), "research"
        add(f"mkt-{_slug(stat)[:24]}-{i}", "Market statistic", stat,
            "https://www.semrush.com/" if str(src).lower() == "semrush" else str(src),
            "research_provider")

    # external authoritative sources — each a distinct citable domain
    for es in rd.get("external_sources") or []:
        if isinstance(es, dict) and es.get("url"):
            name, url = es.get("name") or es["url"], es["url"]
        elif isinstance(es, str) and es.startswith("http"):
            name, url = es, es
        else:
            continue
        add(f"src-{_slug(name)}", "External reference", name, url, "serp")

    return facts
