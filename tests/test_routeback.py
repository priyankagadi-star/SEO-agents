"""Route-back accounting (Phase 0 scope: the deterministic cap mechanism).

Phase 1 extends this file with the mocked-LLM end-to-end case from BUILD-SPEC §11:
poisoned ledger (engines=4) + draft saying "nine engines" → c19 blocks, routes back,
second pass passes or escalates at cap.
"""
import pytest

from graphs.content_graph import NODE_LAYER, apply_route_back, owning_layer
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
