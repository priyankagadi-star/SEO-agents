import pytest

from state import (
    StateValidationError,
    new_content_state,
    validate_diagnosis,
    validate_state,
)


def minimal_content_state(**over):
    s = new_content_state(
        mode="rebuild",
        page_type="feature",
        primary_keyword="chatgpt visibility",
        research_dossier={},
        brand_assets={},
        audience="B2B SEO leads",
        canonical_sources=["https://siftly.ai/features"],
    )
    s.update(over)
    return s


def minimal_diagnosis(**over):
    d = {
        "url": "https://siftly.ai/chatgpt-visibility",
        "page_type": "feature",
        "primary_query": "chatgpt visibility",
        "scorecard": {"answer_first": 1},
        "defects": [{
            "description": "no answer-first lead",
            "owning_step": "c10_hook",
            "severity": "major",
            "fix": "rewrite lead to answer in 60 words",
        }],
        "gap_entity_matrix": {"missing_entities": [], "missing_subtopics": [], "competitor_advantages": []},
        "root_causes": ["thin content"],
        "keep_list": ["Sample Variance differentiator"],
    }
    d.update(over)
    return d


def test_valid_content_state_passes():
    validate_state(minimal_content_state(), after_node="c0_intake_router")


def test_missing_required_field_fails_loud():
    s = minimal_content_state()
    del s["canonical_sources"]
    with pytest.raises(StateValidationError) as exc:
        validate_state(s, after_node="c0_intake_router")
    assert exc.value.node == "c0_intake_router"
    assert any("canonical_sources" in str(e.get("loc", "")) for e in exc.value.errors)


def test_invalid_mode_literal_fails():
    with pytest.raises(StateValidationError):
        validate_state(minimal_content_state(mode="freestyle"), after_node="c0_intake_router")


def test_bad_fact_in_ledger_fails():
    s = minimal_content_state(facts_ledger=[{"id": "x", "status": "maybe"}])
    with pytest.raises(StateValidationError):
        validate_state(s, after_node="c1_source_reconciler")


def test_additive_extra_keys_allowed():
    validate_state(minimal_content_state(some_future_field={"x": 1}), after_node="c8_brief_compiler")


def test_audit_state_inferred_and_validated():
    validate_state({"url": "https://siftly.ai/x"}, after_node="a0_intake")


def test_unrecognizable_state_fails():
    with pytest.raises(StateValidationError):
        validate_state({"hello": "world"}, after_node="a0_intake")


def test_diagnosis_seam_valid():
    validate_diagnosis(minimal_diagnosis())


def test_diagnosis_seam_rejects_bad_page_type():
    with pytest.raises(StateValidationError):
        validate_diagnosis(minimal_diagnosis(page_type="homepage"))


def test_diagnosis_seam_rejects_defect_without_owner():
    bad = minimal_diagnosis()
    bad["defects"] = [{"description": "x", "severity": "minor", "fix": "y"}]
    with pytest.raises(StateValidationError):
        validate_diagnosis(bad)
