"""Research → Facts Ledger seeding (c1) and brief/faq surfacing (c8/c12).

This is the mechanism that lets the agent RAISE its GOAL Information-Gain score:
real market stats + external authoritative sources become citable verified
facts, a market-context section enters the brief, and the FAQ answers real PAA.
"""
import json

from research_facts import facts_from_research

DOSSIER = {
    "market_stats": [
        {"stat": "~8,100 monthly US searches for generative engine optimization", "source": "Semrush"},
        {"stat": "~3,600/mo for answer engine optimization", "source": "Semrush"},
    ],
    "external_sources": [
        {"name": "Search Engine Land — What is GEO", "url": "https://searchengineland.com/x"},
        {"name": "arXiv — GEO research", "url": "https://arxiv.org/abs/2509.08919"},
        {"name": "Google Search Central", "url": "https://developers.google.com/search/y"},
    ],
    "real_questions": ["How to monitor AI search visibility", "What are the best AI visibility tools"],
}


def test_research_facts_market_stats_and_sources():
    facts = facts_from_research(DOSSIER)
    ids = {f["id"] for f in facts}
    assert any(i.startswith("mkt-") for i in ids)
    assert any(i.startswith("src-") for i in ids)
    # external source facts carry the REAL url as source (=> external citation)
    srcs = [f for f in facts if f["id"].startswith("src-")]
    domains = {f["source_url"] for f in srcs}
    assert "https://arxiv.org/abs/2509.08919" in domains
    assert all(f["status"] == "verified" for f in facts)


def test_c1_seeds_research_facts_into_ledger():
    import nodes.content.c1_source_reconciler as c1
    from fakes import ScriptedLLM
    from llm import reset_client, set_client
    set_client(ScriptedLLM({"c1_source_reconciler": json.dumps({"proposed_facts": []})}))
    try:
        out = c1.run({"facts_ledger": [], "brand_profile": {}, "brand_assets": {},
                      "research_dossier": DOSSIER})
    finally:
        reset_client()
    ids = {f["id"] for f in out["facts_ledger"]}
    assert any(i.startswith("mkt-") for i in ids)
    assert any(i.startswith("src-") for i in ids)


def test_c8_brief_adds_market_context_and_carries_sources():
    import nodes.content.c8_brief_compiler as c8
    from fakes import ScriptedLLM
    from llm import reset_client, set_client
    set_client(ScriptedLLM({"c8_brief_compiler": json.dumps(
        {"brief": {"title_direction": "X", "meta_direction": "Y",
                   "structure": [{"id": "hero"}], "internal_link_targets": []}})}))
    try:
        out = c8.run({"page_type": "feature", "facts_ledger": [], "primary_keyword": "ai visibility",
                      "strategy": {}, "unique_insight": "", "serp_feature_targets": [],
                      "gap_entity_matrix": {}, "research_dossier": DOSSIER})
    finally:
        reset_client()
    brief = out["brief"]
    ids = [str(s.get("id")) for s in brief["structure"]]
    assert "market_context" in ids                      # research section added
    assert brief.get("external_sources") and brief.get("market_stats")
    assert brief.get("real_questions")


def test_c12_prefers_real_paa_over_serp_stub():
    import nodes.content.c12_faq as c12
    from fakes import ScriptedLLM
    from llm import reset_client, set_client

    captured = {}

    class Spy(ScriptedLLM):
        def complete(self, prompt, tier, node_id=None):
            if node_id == "c12_faq":
                captured["prompt"] = prompt
            return super().complete(prompt, tier, node_id)

    set_client(Spy({"c12_faq": json.dumps({"faq": [{"q": "Q", "a": "A"}]})}))
    try:
        c12.run({"facts_ledger": [], "outline": {"sections": []}, "primary_keyword": "ai visibility",
                 "serp_analysis": {"paa": ["stub question"]},
                 "research_dossier": {"real_questions": ["How to monitor AI search visibility"]}})
    finally:
        reset_client()
    assert "How to monitor AI search visibility" in captured["prompt"]
    assert "stub question" not in captured["prompt"]      # real PAA wins


def test_seeded_source_facts_raise_external_citation_metric():
    """End-to-end at the gate: citing seeded src-* facts credits external domains."""
    from guardrails import information_gain_score
    from ledger import FactsLedger
    led = FactsLedger(facts_from_research(DOSSIER))
    draft = ("Generative engine optimization is a defined practice (fact:src-search-engine-land-what-is-geo) "
             "with peer-reviewed research (fact:src-arxiv-geo-research) and Google guidance "
             "(fact:src-google-search-central). Demand is real (fact:mkt-8-100-monthly-us-searches-1).")
    r = information_gain_score(draft, led, brand_names=["Acme"], owner_domains=["acme.com"])
    assert r.metrics["external_citations"]["value"] >= 3
