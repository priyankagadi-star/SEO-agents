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


def run_seeded_suite(run_pipeline) -> dict:
    """Execute all seeds against the real pipeline. Phase 2 deliverable."""
    raise NotImplementedError(
        "Seeded-error execution requires the Phase 1 walking skeleton. "
        "Seed definitions above are final; wire them in Phase 2."
    )
