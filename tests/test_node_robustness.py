"""Real models vary their JSON shape; generative nodes must tolerate it.
Regression for the c9 'list outline' crash found in a live run."""
import json

import pytest

from fakes import ScriptedLLM
from llm import reset_client, set_client


def run_with(node_module, node_id, payload, state):
    set_client(ScriptedLLM({node_id: json.dumps(payload)}))
    try:
        return node_module.run(state)
    finally:
        reset_client()


def test_c9_outline_as_bare_list():
    import nodes.content.c9_outline as c9
    state = {"facts_ledger": [], "page_type": "feature", "brief": {}, "gap_entity_matrix": {}}
    # model returned outline as a LIST of sections (the live crash)
    out = run_with(c9, "c9_outline", {"outline": [{"h2": "Prompt explorer"}, "Volume by intent"]}, state)
    secs = out["outline"]["sections"]
    assert len(secs) == 2
    assert all(s.get("id") and s.get("h2") for s in secs)   # id + h2 backfilled


def test_c9_outline_sections_under_structure():
    import nodes.content.c9_outline as c9
    state = {"facts_ledger": [], "page_type": "feature", "brief": {}, "gap_entity_matrix": {}}
    out = run_with(c9, "c9_outline", {"structure": [{"title": "Intro"}]}, state)
    assert out["outline"]["sections"][0]["h2"] == "Intro"


def test_c8_brief_as_list_is_coerced():
    import nodes.content.c8_brief_compiler as c8
    state = {"facts_ledger": [], "page_type": "feature", "primary_keyword": "x",
             "strategy": {}, "unique_insight": "", "gap_entity_matrix": {}, "serp_feature_targets": []}
    # model put a list under "brief" (parse_json always yields a dict envelope;
    # only its values vary in shape)
    out = run_with(c8, "c8_brief_compiler", {"brief": ["Hero", "Benefits"]}, state)
    assert isinstance(out["brief"], dict) and "structure" in out["brief"]


def test_c11_alternate_body_keys():
    import nodes.content.c11_section_drafter as c11
    state = {"facts_ledger": [], "outline": {"sections": [{"id": "s1", "h2": "H"}]},
             "intent_contract": {}, "brand_voice": {}}
    out = run_with(c11, "c11_section_drafter", {"section_id": "s1", "content": "Body via 'content' key."}, state)
    assert out["sections"]["s1"] == "Body via 'content' key."


def test_c12_faq_normalizes_shapes():
    import nodes.content.c12_faq as c12
    state = {"facts_ledger": [], "outline": {"sections": []}, "primary_keyword": "x", "serp_analysis": {}}
    # dict-map form {question: answer}
    out = run_with(c12, "c12_faq", {"faq": {"What is it?": "A thing."}}, state)
    assert out["faq"] == [{"q": "What is it?", "a": "A thing."}]
    # question/answer keys + nested acceptedAnswer
    out = run_with(c12, "c12_faq", {"faq": [{"question": "Q1", "answer": "A1"},
                                            {"name": "Q2", "acceptedAnswer": {"text": "A2"}}]}, state)
    assert {"q": "Q1", "a": "A1"} in out["faq"] and {"q": "Q2", "a": "A2"} in out["faq"]


def test_c15_media_plan_string_items():
    import nodes.content.c15_media as c15
    state = {"primary_keyword": "ai prompt analytics", "outline": {"sections": [{"id": "s1", "h2": "X"}]},
             "brief": {"media_plan": ["a product screenshot", "a diagram"]}, "brand_assets": {}, "human_checkpoints": []}
    out = c15.run(state)  # must not crash on string media_plan items
    assert "media_manifest" in out
    assert any("screenshot" in h.lower() for h in out["human_checkpoints"])


def test_c16_cuts_unverified_sentences_not_blocks():
    import nodes.content.c16_editorial as c16
    state = {"facts_ledger": [], "human_checkpoints": [],
             "outline": {"sections": [{"id": "s1", "h2": "X"}]},
             "lead": "Siftly tracks 9 AI engines. [VERIFY: customer count] customers trust us.",
             "sections": {"s1": "It publishes to your CMS. We saved teams [VERIFY: hours] hours."},
             "faq": [{"q": "How many engines?", "a": "Nine."}]}
    out = c16.run(state)
    assert "[VERIFY" not in out["draft"]                  # nothing unverified ships
    assert "Siftly tracks 9 AI engines" in out["draft"]   # verified sentence kept
    assert "It publishes to your CMS" in out["draft"]
    assert any("cut from draft" in h for h in out["human_checkpoints"])  # surfaced, not lost


def test_c16_strips_verify_note_with_internal_period_keeps_grounded_claim():
    """A [VERIFY] note containing 'e.g.' must not survive via a bad sentence
    split; a grounded sentence keeps its claim with the note stripped."""
    import nodes.content.c16_editorial as c16
    state = {"facts_ledger": [], "human_checkpoints": [],
             "outline": {"sections": [{"id": "s1", "h2": "X"}]},
             "lead": "Siftly publishes to your CMS (fact:generates) [VERIFY: platform names, e.g. WordPress/Webflow unresolved].",
             "sections": {"s1": "We saved teams [VERIFY: hours] hours."}, "faq": []}
    out = c16.run(state)
    assert "[VERIFY" not in out["draft"]                       # nothing unverified ships
    assert "Siftly publishes to your CMS" in out["draft"]      # grounded claim kept
    assert "(fact:generates)" in out["draft"]
    assert "We saved teams" not in out["draft"]                # ungrounded claim cut


def test_brand_facts_seed_engine_count():
    from brand_facts import facts_from_brand
    facts = facts_from_brand(
        {"how_it_works_verified": {"engines_count": 9, "engines": ["ChatGPT", "Groq"]}}, {})
    ec = next(f for f in facts if f["id"] == "engines-count")
    assert ec["status"] == "verified" and ec["value"].startswith("9") and ec.get("claim_pattern")


def test_c20_cta_as_dict_does_not_crash():
    """Real models sometimes return brief.cta as a dict, not a string."""
    import nodes.content.c20_render_critic as c20
    out = c20.run({"facts_ledger": [], "draft": "Body copy.", "page_type": "feature",
                   "outline": {"sections": []}, "media_manifest": [],
                   "brief": {"title_direction": "X", "meta_direction": "Y",
                             "cta": {"text": "Book a demo today now please"}}})
    assert "_guardrails" in out   # ran to completion, no AttributeError on cta.split()


def test_c22_byline_and_last_updated_in_every_package():
    """E-E-A-T: every page must carry author + last-updated (or surface a checkpoint)."""
    import nodes.content.c22_packager as c22
    out = c22.run({
        "primary_keyword": "ai prompt analytics", "brief": {"title_direction": "X", "meta_direction": "Y"},
        "draft": "body", "schema_jsonld": {"@graph": [{"@type": "WebPage", "name": "X", "url": "/x"}]},
        "brand_assets": {"author": {"name": "Chalam PVS", "title": "Founder", "company": "Siftly"}},
        "human_checkpoints": [], "verify_list": [], "_runlog": [],
    })
    pkg = out["package_out"]
    assert pkg["byline"]["name"] == "Chalam PVS"
    assert pkg["byline_line"].startswith("Written by Chalam PVS · Founder · Siftly · Last updated")
    assert pkg["last_updated"]                 # "24 June 2026"
    # E-E-A-T schema: author + dateModified inside the JSON-LD page entity
    page_node = pkg["schema_jsonld"]["@graph"][0]
    assert page_node["author"]["name"] == "Chalam PVS"
    assert page_node["dateModified"]           # ISO date


def test_c22_missing_author_surfaces_checkpoint_not_fakes_one():
    """No author in brand_assets → human checkpoint, never invented."""
    import nodes.content.c22_packager as c22
    out = c22.run({
        "primary_keyword": "x", "brief": {}, "draft": "body",
        "schema_jsonld": {"@graph": [{"@type": "WebPage"}]},
        "brand_assets": {}, "human_checkpoints": [], "verify_list": [], "_runlog": [],
    })
    pkg = out["package_out"]
    assert pkg["byline"] is None
    assert any("no author" in h.lower() for h in pkg["human_checkpoints"])
    # schema dateModified still set (freshness ≠ author)
    assert pkg["schema_jsonld"]["@graph"][0]["dateModified"]
