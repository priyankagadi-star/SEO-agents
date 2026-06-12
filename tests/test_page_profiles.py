"""Per-page-type structure contracts (BUILD-SPEC §4 page_type literal)."""
import pytest

from page_profiles import PROFILES, get_profile


def test_every_diagnosis_page_type_has_a_profile():
    # the six page_type literals from state.Diagnosis
    for pt in ("feature", "blog-listicle", "guide", "comparison", "landing", "glossary"):
        assert pt in PROFILES
        assert PROFILES[pt].required_blocks()


def test_profiles_are_distinct_per_type():
    sigs = {pt: tuple(b.id for b in p.required_blocks()) for pt, p in PROFILES.items()}
    # each type's block set is unique — they really do differ in shape
    assert len(set(sigs.values())) == len(sigs)
    # the defining blocks exist where they should
    assert "at_a_glance" in sigs["comparison"]      # comparison table
    assert "definition" in sigs["glossary"]          # definition-first
    assert "steps" in sigs["guide"]                  # step-by-step
    assert "differentiators" in sigs["feature"]


def test_schema_types_are_type_specific():
    assert "SoftwareApplication" in get_profile("feature").schema_types
    assert "DefinedTerm" in get_profile("glossary").schema_types
    assert "HowTo" in get_profile("guide").schema_types
    assert "ItemList" in get_profile("blog-listicle").schema_types


def test_word_budget_defers_to_config_then_default():
    assert get_profile("feature").word_budget == [1400, 1800]   # from config.yaml
    assert get_profile("glossary").word_budget == [800, 1400]   # now in config too
    assert get_profile("landing").word_budget == [600, 1200]


def test_unknown_type_falls_back_to_feature():
    assert get_profile("zzz").page_type == "feature"
    assert get_profile(None).page_type == "feature"


def test_missing_blocks_detection():
    profile = get_profile("comparison")
    # a draft with everything but the comparison table
    draft = ("## Verdict\nTool A wins. ## Criteria\nWe judged on price. "
             "## Head-to-head\nA vs B. ## Pros and cons\nstrengths. "
             "## Who should choose\nbest for teams. ## FAQ\nquestions")
    missing = [b.id for b in profile.missing_blocks(draft, None)]
    assert "at_a_glance" in missing
    assert "verdict" not in missing


def test_comparison_without_table_flagged_by_render_critic():
    from nodes.content.c20_render_critic import run
    state = {
        "page_type": "comparison",
        "brief": {"title_direction": "A vs B", "meta_direction": "compare", "cta": "Pick"},
        "draft": "## Verdict\nA wins. ## Criteria\nprice. ## Head to head\nA vs B. "
                 "## Pros\ngood ## Who should choose\nteams ## FAQ\nq",
        "media_manifest": [], "outline": {"sections": []}, "facts_ledger": [],
    }
    failures = run(state)["render_report"]["failures"]
    structural = [f for f in failures if "missing required block" in f["description"]]
    assert any("comparison table" in f["description"].lower()
               or "at-a-glance" in f["description"].lower()
               or "at a glance" in f["description"].lower() for f in structural)
    # structure gaps are reported (major) but do not hard-block the run
    assert all(f["severity"] != "blocker" for f in structural)


def test_glossary_schema_emits_defined_term():
    from nodes.content.c18_schema import run
    out = run({
        "page_type": "glossary", "primary_keyword": "ai citation tracking",
        "lead": "AI citation tracking is how often AI engines cite your brand.",
        "brand_assets": {}, "faq": [], "outline": {"sections": []},
        "brief": {"title_direction": "AI Citation Tracking"},
    })
    types = [b.get("@type") for b in out["schema_jsonld"]["@graph"]]
    assert "DefinedTerm" in types


def test_feature_brief_seeds_required_structure():
    """c8 deterministically backfills required blocks even if the model omits them."""
    import json

    from fakes import ScriptedLLM
    from llm import reset_client, set_client
    import nodes.content.c8_brief_compiler as c8

    # model returns a deliberately thin brief (one section only)
    set_client(ScriptedLLM({"c8_brief_compiler": json.dumps(
        {"brief": {"title_direction": "X", "meta_direction": "Y",
                   "structure": [{"id": "intro"}], "internal_link_targets": []}})}))
    try:
        out = c8.run({"page_type": "comparison", "facts_ledger": [],
                      "primary_keyword": "a vs b", "strategy": {}, "unique_insight": "",
                      "gap_entity_matrix": {}, "serp_feature_targets": []})
    finally:
        reset_client()
    ids = {s.get("id") for s in out["brief"]["structure"]}
    # every required comparison block is present despite the thin model output
    assert {"at_a_glance", "verdict", "head_to_head"} <= ids
    assert out["brief"]["schema_types"]
