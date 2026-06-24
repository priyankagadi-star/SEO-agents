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
