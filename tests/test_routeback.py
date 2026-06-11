"""Route-back accounting (Phase 0 scope: the deterministic cap mechanism).

Phase 1 extends this file with the mocked-LLM end-to-end case from BUILD-SPEC §11:
poisoned ledger (engines=4) + draft saying "nine engines" → c19 blocks, routes back,
second pass passes or escalates at cap.
"""
import pytest

from graphs.content_graph import (
    NODE_LAYER,
    apply_route_back,
    build_content_graph,
    owning_layer,
)
from state import EscalateToHuman, new_content_state


def fresh_state():
    return new_content_state(
        mode="rebuild",
        page_type="feature",
        primary_keyword="chatgpt visibility",
        research_dossier={},
        brand_assets={},
        audience="B2B",
        canonical_sources=["https://siftly.ai/features"],
    )


def test_route_back_increments_count():
    s = fresh_state()
    apply_route_back(s, "L3", cap=2)
    assert s["route_back_count"]["L3"] == 1
    apply_route_back(s, "L3", cap=2)
    assert s["route_back_count"]["L3"] == 2


def test_route_back_escalates_at_cap():
    s = fresh_state()
    apply_route_back(s, "L3", cap=2)
    apply_route_back(s, "L3", cap=2)
    with pytest.raises(EscalateToHuman) as exc:
        apply_route_back(s, "L3", cap=2)
    assert exc.value.layer == "L3"
    assert exc.value.cap == 2


def test_route_back_counts_are_per_layer():
    s = fresh_state()
    apply_route_back(s, "L3", cap=2)
    apply_route_back(s, "L1", cap=2)
    assert s["route_back_count"] == {"L3": 1, "L1": 1}


def test_owning_layer_lookup():
    assert owning_layer("c11_section_drafter") == "L3"
    assert owning_layer("c7_strategist") == "L1"
    assert NODE_LAYER["c19_critic"] == "L6"
    with pytest.raises(KeyError):
        owning_layer("c99_unknown")


# ---------------------------------------------------------------------------
# Phase 1 acceptance: mocked-LLM end-to-end route-back (BUILD-SPEC §11)
# ---------------------------------------------------------------------------

def rebuild_state():
    return new_content_state(
        mode="rebuild",
        page_type="feature",
        target_url="https://siftly.ai/chatgpt-visibility",
        primary_keyword="chatgpt visibility tracking",
        research_dossier={},
        brand_assets={"author": {"name": "A. Lee", "credentials": "Head of SEO"}},
        audience="B2B SEO leads",
        canonical_sources=["https://siftly.ai/features"],
        gap_entity_matrix={"missing_entities": ["AI Overview citation share"],
                           "missing_subtopics": [], "competitor_advantages": []},
        keep_list=["Sample Variance differentiator"],
        failure_modes=["thin answer-first lead", "vague engine coverage"],
    )


def _run(script_kwargs, thread_id):
    from langgraph.checkpoint.memory import MemorySaver
    from fakes import ScriptedLLM, make_rebuild_script
    from llm import reset_client, set_client

    set_client(ScriptedLLM(make_rebuild_script(**script_kwargs)))
    try:
        graph = build_content_graph(checkpointer=MemorySaver())
        return graph.invoke(
            rebuild_state(),
            config={"configurable": {"thread_id": thread_id}, "recursion_limit": 100},
        )
    finally:
        reset_client()


def test_poisoned_draft_blocks_then_passes_on_routeback():
    """engines locked at 4 + first draft says 'nine engines' → c19 blocks,
    routes back to L3, corrected second pass passes and packages."""
    result = _run({"poison_first_pass": True}, "rb-pass")
    # c19 blocked at least once and routed back to L3
    assert result["route_back_count"].get("L3", 0) >= 1
    # final verdict passes and a package was produced
    assert result["critic_report"]["verdict"] == "pass"
    assert result["package_out"]["full_copy"]
    # the contradiction is gone from the shipped draft
    assert "nine ai engines" not in result["draft"].lower()
    # the locked fact survived as verified
    engines = next(f for f in result["facts_ledger"] if f["id"] == "engines-count")
    assert engines["status"] == "verified" and engines["value"].startswith("4")


def test_persistent_poison_escalates_at_cap():
    """If the drafter never corrects, route-backs hit the cap → EscalateToHuman."""
    with pytest.raises(EscalateToHuman) as exc:
        _run({"poison_always": True}, "rb-escalate")
    assert exc.value.layer == "L3"


def test_clean_run_packages_without_routeback():
    result = _run({"poison_first_pass": False}, "rb-clean")
    assert result["route_back_count"].get("L3", 0) == 0
    assert result["critic_report"]["verdict"] == "pass"
    pkg = result["package_out"]
    assert len(pkg["title_variants"]) == 3
    assert all(len(t) <= 60 for t in pkg["title_variants"])
    assert len(pkg["meta"]) <= 155
    assert len(pkg["internal_links"]) >= 4
    assert len(result["faq"]) >= 5
