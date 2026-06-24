"""Quality gates added after the live Siftly run: AI-tells, anaphora,
vague-comparative claims, and the structural-flexibility upgrade."""
import re

from guardrails import (
    ai_tell_check,
    anaphora_check,
    vague_comparative_check,
)


def test_ai_tell_blocks_dense_filler():
    draft = ("In today's world, AI fundamentally transforms business into a "
             "seamless paradigm shift, reshaping how we leverage cutting-edge "
             "platforms to navigate the complex landscape.")
    v = ai_tell_check(draft)
    assert v and v[0].severity == "blocker"   # >threshold = blocker
    assert "fundamentally" in v[0].detail or "reshaping" in v[0].detail


def test_ai_tell_clean_text_passes():
    assert ai_tell_check("Siftly tracks brand visibility across 9 AI engines. "
                          "Domu moved from invisible to #9 in a month.") == []


def test_ai_tell_one_two_hits_is_minor_not_blocker():
    """Real prose can have one 'fundamentally' — flag as minor, don't block."""
    v = ai_tell_check("AI search is fundamentally different from traditional search.")
    assert v and v[0].severity == "major"     # below threshold = major not blocker


def test_anaphora_catches_you_cant_pattern():
    """The exact AI-rhythm tell that shipped in the Siftly draft."""
    draft = ("You can't see whether your brand shows up. You can't tell which "
             "competitors get cited. You don't know which prompts you win. "
             "You don't know which sources AI trusts. You can't measure impact. "
             "You can't iterate. You can't capture this channel.")
    v = anaphora_check(draft)
    assert v and "unigrams" in v[0].detail and "you" in v[0].detail


def test_anaphora_varied_openers_pass():
    draft = ("Siftly tracks 9 engines. Buyers ask AI before Google. "
             "Domu moved from invisible to ranking #9. Conversations turns "
             "AI search into a measurable channel.")
    assert anaphora_check(draft) == []


def test_vague_comparative_without_name_fails():
    v = vague_comparative_check("Most AI visibility tools just show dashboards.")
    assert v and v[0].kind == "vague_comparative"


def test_vague_comparative_with_named_competitor_passes():
    assert vague_comparative_check(
        "Most AI visibility tools — Profound, Otterly, and Mention — just show dashboards."
    ) == []


def test_vague_comparative_with_fact_ref_passes():
    assert vague_comparative_check(
        "Most AI visibility tools (fact:engines-count) just show dashboards."
    ) == []


# ---- structural flexibility: c8 surfaces candidate additions + trends -----

def test_c8_surfaces_candidate_additions_and_trends():
    """The template is the floor; competitor headings + trend signals are
    candidates the strategist may ADD on top."""
    import json
    import nodes.content.c8_brief_compiler as c8
    from fakes import ScriptedLLM
    from llm import reset_client, set_client

    captured = {"prompt": ""}

    class Spy(ScriptedLLM):
        def complete(self, prompt, tier, node_id=None):
            if node_id == "c8_brief_compiler":
                captured["prompt"] = prompt
            return super().complete(prompt, tier, node_id)

    set_client(Spy({"c8_brief_compiler": json.dumps(
        {"brief": {"title_direction": "X", "meta_direction": "Y",
                   "structure": [{"id": "hero"}], "internal_link_targets": []}})}))
    try:
        c8.run({
            "page_type": "feature", "facts_ledger": [],
            "primary_keyword": "ai prompt analytics",
            "strategy": {}, "unique_insight": "", "serp_feature_targets": [],
            "gap_entity_matrix": {
                "missing_subtopics": [
                    "today's AI-search trend",
                    "where this fits in your stack",
                    "use cases for B2B vs ecommerce",
                ]
            },
            "research_dossier": {
                "trend_signals": ["Google AI Mode rolled out 2026", "ChatGPT Search GA"]
            },
        })
    finally:
        reset_client()
    p = captured["prompt"]
    assert "today's AI-search trend" in p          # competitor heading surfaced
    assert "Google AI Mode rolled out 2026" in p   # trend signal surfaced
    # CONTRACT: required blocks still present (the floor)
    for required in ("problem", "differentiators", "proof", "faq", "cta"):
        assert required in p.lower()
