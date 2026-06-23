"""The 6 poisoned inputs (BUILD-SPEC §9).

The suite PASSES only if every seed is flagged/blocked; it FAILS if any ships
silently. Seed definitions are data; execution (run_seeded_suite) drives the
real pipeline and lands with Phase 2 (seeds 1,2,3,5) and Phase 4 (seeds 4,6).
"""
from __future__ import annotations

SEEDS = [
    {
        "id": 1,
        "name": "engine_count_poison",
        "poison": {"research_dossier": {"claims": ["Siftly monitors 9 AI engines"]}},
        "expect": "conflict surfaced + fact_diff blocker (canonical locks engines-count=4)",
        "detector": ["c1_source_reconciler", "c19_critic"],
    },
    {
        "id": 2,
        "name": "fabricated_stat",
        "poison": {"research_dossier": {"claims": ["73% of CMOs plan to cut organic budgets"]}},
        "expect": "stat becomes [VERIFY:…] or is cut; never ships bare",
        "detector": ["c13_evidence", "flag_dont_fill"],
    },
    {
        "id": 3,
        "name": "unpermissioned_testimonial",
        "poison": {"brand_assets": {"testimonials": [
            {"quote": "Siftly doubled our AI citations", "author": "J. Doe", "permission": False}
        ]}},
        "expect": "testimonial absent from copy AND from Review schema",
        "detector": ["c14_eeat", "c18_schema"],
    },
    {
        "id": 4,
        "name": "dropped_keep_list_item",
        "poison": {"keep_list": ["Sample Variance differentiator"], "strategist_nudge": "drop it"},
        "expect": "c9 entity-coverage or c19 critic fails the run",
        "detector": ["c9_outline", "c19_critic"],
    },
    {
        "id": 5,
        "name": "canonical_disagreement",
        "poison": {"canonical_sources_content": {
            "https://siftly.ai/features": "4 engines", "https://siftly.ai/": "6 engines"
        }},
        "expect": "source_precedence surfaces; NEVER auto-picks",
        "detector": ["c1_source_reconciler", "source_precedence"],
    },
    {
        "id": 6,
        "name": "sibling_product_scope_creep",
        "poison": {"research_dossier": {"claims": ["Citation Outreach finds journalists to pitch"]},
                   "scoped_to": "different URL"},
        "expect": "linked-out, not claimed as this page's feature",
        "detector": ["c7_strategist", "c19_critic"],
    },
]


def _seed1_engine_count() -> tuple[bool, str]:
    """fact_diff must block a draft contradicting a locked fact."""
    from guardrails import fact_diff
    from ledger import FactsLedger
    led = FactsLedger()
    led.add({"id": "engines-count", "claim": "engines", "value": "4 (ChatGPT, Claude, Perplexity, Google AI Overviews)",
             "source_url": "https://siftly.ai/features", "verified_by": "c1", "status": "verified",
             "claim_pattern": r"\b(\d+|nine)\s+(?:major\s+)?AI engines"})
    v = fact_diff("Siftly monitors 9 AI engines.", led)
    return (any(x.kind == "fact_contradiction" for x in v),
            v[0].detail if v else "NOT CAUGHT — '9 engines' shipped against locked value 4")


def _seed2_fabricated_stat() -> tuple[bool, str]:
    """flag_dont_fill must catch an unsourced stat (empty ledger)."""
    from guardrails import flag_dont_fill
    from ledger import FactsLedger
    v = flag_dont_fill("73% of CMOs plan to cut organic budgets.", FactsLedger())
    return (any(x.kind == "unsourced_number" for x in v),
            v[0].detail if v else "NOT CAUGHT — bare 73% shipped")


def _seed3_unpermissioned_testimonial() -> tuple[bool, str]:
    """c14 must exclude permission!=true testimonials; c18 must emit no Review."""
    import nodes.content.c14_eeat as c14
    import nodes.content.c18_schema as c18
    brand = {"author": {"name": "A. Lee"}, "testimonials": [
        {"quote": "Siftly doubled our AI citations", "author": "J. Doe", "permission": False}]}
    eeat = c14.run({"brand_assets": brand, "human_checkpoints": []})["_eeat"]
    schema = c18.run({"page_type": "feature", "primary_keyword": "x", "brand_assets": brand,
                      "faq": [], "outline": {"sections": []}, "brief": {}, "lead": ""})["schema_jsonld"]
    reviews = [b for b in schema.get("@graph", []) if b.get("@type") in ("Review", "AggregateRating")]
    ok = not eeat["testimonials_used"] and not reviews
    return (ok, "excluded from copy + schema" if ok else "LEAKED unpermissioned testimonial")


def _seed4_dropped_keep_list() -> tuple[bool, str]:
    """c19 must fail when a keep_list item is missing from the draft."""
    import nodes.content.c19_critic as c19
    report = c19.run({"facts_ledger": [], "draft": "A draft with no differentiator at all.",
                      "keep_list": ["Sample Variance differentiator"]})["critic_report"]
    blocked = any(f["owning_step"] == "c9_outline" and f["severity"] == "blocker"
                  for f in report["failures"])
    return (report["verdict"] == "fail" and blocked,
            "run failed on dropped keep-list item" if blocked else "NOT CAUGHT — keep-list item dropped silently")


def _seed5_canonical_disagreement() -> tuple[bool, str]:
    """Ledger must surface a conflict; source_precedence must never auto-pick."""
    from guardrails import source_precedence
    from ledger import FactsLedger
    led = FactsLedger()
    base = {"id": "engines-count", "claim": "engines", "source_url": "https://siftly.ai/features",
            "verified_by": "c1", "status": "verified"}
    led.add({**base, "value": "4 engines"})
    led.add({**base, "value": "6 engines", "source_url": "https://siftly.ai/"})
    conflicted = led.get("engines-count")["status"] == "conflict"
    decision = source_precedence({"fact_id": "engines-count", "options": [
        {"value": "4", "source_class": "feature_page"}, {"value": "6", "source_class": "marketing"}]},
        ["owner", "docs", "feature_page", "marketing", "audit"])
    never_autopicks = decision["action"] == "surface" and "resolved" not in decision
    return (conflicted and never_autopicks,
            "conflict surfaced; precedence recommends but never auto-picks"
            if conflicted and never_autopicks else "NOT CAUGHT — conflict auto-resolved")


def _seed6_sibling_scope_creep() -> tuple[bool, str]:
    """intent_boundary_check must flag a section owned by a sibling URL."""
    from guardrails import intent_boundary_check
    cluster = {"spokes": [
        {"url": "https://siftly.ai/brand-monitoring", "intent": "ai brand monitoring",
         "keywords": ["brand monitoring"]},
        {"url": "https://siftly.ai/citation-outreach", "intent": "citation outreach",
         "keywords": ["citation outreach", "pitch journalists", "find journalists"]}]}
    outline = {"sections": [{"h2": "Citation Outreach: find journalists to pitch",
                             "intent": "citation outreach pitch journalists"}]}
    v = intent_boundary_check(outline, cluster, page_intent="ai brand monitoring",
                              current_url="https://siftly.ai/brand-monitoring")
    return (any(x.kind == "intent_trespass" for x in v),
            v[0].detail if v else "NOT CAUGHT — sibling feature claimed, not linked")


_CHECKS = {
    1: _seed1_engine_count, 2: _seed2_fabricated_stat, 3: _seed3_unpermissioned_testimonial,
    4: _seed4_dropped_keep_list, 5: _seed5_canonical_disagreement, 6: _seed6_sibling_scope_creep,
}


def run_seeded_suite() -> dict:
    """Run all 6 poisons against the REAL guardrails/nodes. Needs no gold files
    and no model calls. Passes only if every poison is caught."""
    results = []
    for seed in SEEDS:
        caught, evidence = _CHECKS[seed["id"]]()
        results.append({"id": seed["id"], "name": seed["name"], "caught": caught,
                        "expect": seed["expect"], "evidence": evidence})
    return {"passed": all(r["caught"] for r in results),
            "caught": sum(r["caught"] for r in results), "total": len(results),
            "results": results}
