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


def test_c6_coerces_dict_human_checkpoints_to_strings():
    """Real models return human_checkpoints as structured dicts; state expects
    list[str], and Pydantic crashes if dicts leak through."""
    import json
    import nodes.content.c6_brand_loader as c6
    from fakes import ScriptedLLM
    from llm import set_client, reset_client
    payload = {"c6_brand_loader": json.dumps({"brand_voice": {"voice": "x"},
        "human_checkpoints": [
            {"id": "x", "description": "[VERIFY: do X]"},
            {"id": "y", "category": "Assets", "issue": "Y", "action": "[VERIFY: do Y]"},
            "[HUMAN] plain string survives",
        ]})}
    set_client(ScriptedLLM(payload))
    try:
        out = c6.run({"brand_assets": {"author": {"name": "X"}}, "facts_ledger": [],
                      "brand_profile": {}, "human_checkpoints": []})
    finally:
        reset_client()
    assert all(isinstance(h, str) for h in out["human_checkpoints"])
    assert any("[VERIFY: do X]" in h for h in out["human_checkpoints"])
    assert "[HUMAN] plain string survives" in out["human_checkpoints"]


def test_c20_seo_length_contracts_min_max_flagged():
    """SEO length checks: title min, meta min, H1 min/max, AIO answer block,
    H2 / FAQ Q&A / paragraph / URL slug — each gets a minor finding when out
    of range."""
    import nodes.content.c20_render_critic as c20
    out = c20.run({
        "facts_ledger": [], "page_type": "feature", "media_manifest": [],
        "brief": {"title_direction": "AI",                                     # too short (<40)
                  "meta_direction": "Short meta.",                              # too short (<120)
                  "cta": "Demo"},
        "draft": "x" * 700,                                                     # paragraph > 600
        "outline": {"sections": [{"id": "s1", "h2": "Short"},                   # H2 too short
                                  {"id": "s2", "h2": "ok descriptive heading about thing"}]},
        "sections": {"answer_first": "tiny."},                                  # AIO < 200
        "faq": [{"q": "Q?", "a": "A"},                                          # Q too short, A too short
                {"q": "How do I track brand mentions across AI engines like ChatGPT and Gemini?",
                 "a": "Run the prompts your buyers ask and read the responses to see where your brand appears."}],
        "target_url": "/features/this-is-a-very-long-url-slug-that-exceeds-sixty-characters-totally",
    })
    descs = [f["description"] for f in out["render_report"]["failures"]]
    assert any("title direction" in d and "< 40" in d for d in descs)
    assert any("meta direction" in d and "< 120" in d for d in descs)
    assert any("AIO answer block" in d for d in descs)
    assert any("H2 's1'" in d and "< 20" in d for d in descs)
    assert any("FAQ Q[1]" in d and "< 30" in d for d in descs)
    assert any("FAQ A[1]" in d and "< 100" in d for d in descs)
    assert any("longest paragraph" in d for d in descs)
    assert any("URL slug" in d for d in descs)


def test_c20_seo_length_clean_when_within_range():
    """Clean inputs surface no SEO-length findings."""
    import nodes.content.c20_render_critic as c20
    out = c20.run({
        "facts_ledger": [], "page_type": "feature", "media_manifest": [],
        "brief": {"title_direction": "AI Visibility Platform for B2B SaaS Brands",
                  "meta_direction": ("Track how ChatGPT, Gemini, Perplexity, Claude and Google AI "
                                     "Overviews mention your brand. Generate the content AI cites."),
                  "cta": "Book a demo"},
        "draft": "Normal paragraph.\n\nAnother normal one.",
        "outline": {"sections": [{"id": "problem", "h2": "Why AI search shapes B2B buyer decisions"}]},
        "sections": {"answer_first": "x" * 280},   # AIO in [200,400]
        "faq": [{"q": "How do I track my brand visibility across AI engines?",
                 "a": ("Run the prompts your buyers actually ask and read the answers to see "
                       "where you stand. Tools like Siftly automate this on a schedule.")}],
        "target_url": "/features/ai-visibility",
    })
    descs = [f["description"] for f in out["render_report"]["failures"]]
    seo_descs = [d for d in descs if any(k in d for k in
                ("title direction", "meta direction", "H1 ", "AIO answer", "H2 '",
                 "FAQ Q", "FAQ A", "paragraph", "URL slug", "image alt"))]
    assert seo_descs == [], f"unexpected SEO findings: {seo_descs}"


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
