"""Rubric scorer (BUILD-SPEC §9): 10 deterministic checks, 0/1/2 each.

Pass bar: package score ≥ rubric_pass_pct% of the gold package's score on the
same rubric (config.yaml, default 85).
"""
from __future__ import annotations

import re

from guardrails import VERIFY_PAT, fact_diff, grounding_check
from ledger import FactsLedger


def _score_answer_first(copy: str) -> int:
    first_para = next((p for p in copy.split("\n\n") if p.strip() and not p.strip().startswith("#")), "")
    words = len(first_para.split())
    if 0 < words <= 60:
        return 2
    return 1 if words <= 90 else 0


def _score_unique_insight(state: dict, ledger: FactsLedger) -> int:
    insight = state.get("unique_insight") or ""
    if not insight:
        return 0
    return 2 if not grounding_check([insight], ledger) else 1


def _score_entity_coverage(copy: str, state: dict) -> int:
    gap = state.get("gap_entity_matrix") or {}
    required = list(gap.get("missing_entities", [])) + list(state.get("keep_list") or [])
    if not required:
        return 2
    covered = sum(1 for e in required if re.search(re.escape(str(e)), copy, re.I))
    ratio = covered / len(required)
    return 2 if ratio == 1.0 else (1 if ratio >= 0.8 else 0)


def _score_no_unresolved_verify(copy: str) -> int:
    return 2 if not VERIFY_PAT.search(copy) else 0


def _score_fact_diff(copy: str, ledger: FactsLedger) -> int:
    return 2 if not fact_diff(copy, ledger) else 0


def _score_faq(package: dict) -> int:
    faq = package.get("faq") or []
    if len(faq) < 5:
        return 0
    questions = [str(f.get("q") or f.get("question") or "").lower().strip() for f in faq]
    return 2 if len(set(questions)) == len(questions) else 1


def _score_title_meta(package: dict) -> int:
    titles = package.get("title_variants") or []
    meta = package.get("meta") or ""
    titles_ok = bool(titles) and all(len(t) <= 60 for t in titles)
    meta_ok = 0 < len(meta) <= 155
    return 2 if (titles_ok and meta_ok) else (1 if (titles_ok or meta_ok) else 0)


def _score_media_manifest(package: dict) -> int:
    manifest = package.get("media_manifest") or []
    if not manifest:
        return 0
    issues = 0
    for item in manifest:
        src = str(item.get("filename", ""))
        if src.startswith("data:"):
            return 0  # base64 is an automatic fail
        if not item.get("alt"):
            issues += 1
        if not re.search(r"[a-z]+(-[a-z0-9]+)+", src):
            issues += 1
    hero = manifest[0]
    if hero.get("loading") == "lazy":
        issues += 1
    return 2 if issues == 0 else 1


def _score_schema(package: dict, copy: str) -> int:
    schema = package.get("schema_jsonld") or {}
    if not schema:
        return 0
    graph = schema.get("@graph", [schema])
    faq_blocks = [b for b in graph if isinstance(b, dict) and b.get("@type") == "FAQPage"]
    for block in faq_blocks:
        for entity in block.get("mainEntity", []):
            q = entity.get("name", "")
            if q and q.lower() not in copy.lower():
                return 1  # schema FAQ text diverges from visible text
    return 2


def _score_internal_links(package: dict) -> int:
    links = package.get("internal_links") or []
    return 2 if len(links) >= 4 else (1 if len(links) >= 2 else 0)


def score_output(package_out: dict, state: dict | None = None) -> dict:
    """Score a package_out. Returns {items: {name: 0|1|2}, total, max, pct}."""
    state = state or {}
    ledger = FactsLedger(list(state.get("facts_ledger") or []))
    copy = package_out.get("full_copy") or ""
    items = {
        "answer_first_lead": _score_answer_first(copy),
        "unique_insight_grounded": _score_unique_insight(state, ledger),
        "entity_coverage": _score_entity_coverage(copy, state),
        "zero_unresolved_verify": _score_no_unresolved_verify(copy),
        "fact_diff_clean": _score_fact_diff(copy, ledger),
        "faq_5_deduped": _score_faq(package_out),
        "title_meta_limits": _score_title_meta(package_out),
        "image_manifest": _score_media_manifest(package_out),
        "schema_valid_faq_match": _score_schema(package_out, copy),
        "internal_links": _score_internal_links(package_out),
    }
    total = sum(items.values())
    return {"items": items, "total": total, "max": 20, "pct": round(100 * total / 20, 1)}


def passes_vs_gold(package_score: dict, gold_score: dict, pass_pct: int = 85) -> bool:
    if gold_score["total"] == 0:
        return False
    return package_score["total"] >= (pass_pct / 100) * gold_score["total"]
