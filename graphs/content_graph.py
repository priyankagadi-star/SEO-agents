"""Pipeline B wiring — content generation graph (BUILD-SPEC §5b).

Topology (declared as data so tests and docs can't drift from the wiring):
c0 → [c1, c2, (c3→c4→c5), c6 parallel] → c7 → c8 → c9
   → [c10, c11×N fan-out, c12 parallel] → [c13, c14, c15 parallel]
   → c16 → [c17, c18 parallel] → [c19, c20, (c21 rebuild) parallel] → gate → c22

Phase 0 ships the topology, layer map and route-back mechanism; node modules
are added in Phases 1/4 and the builder wires whatever the phase requires.
"""
from __future__ import annotations

import importlib
from typing import Callable

from state import ContentState, EscalateToHuman, validate_state

# node id -> layer (BUILD-SPEC §5b)
NODE_LAYER: dict[str, str] = {
    "c0_intake_router": "L0",
    "c1_source_reconciler": "L0",
    "c2_cannibalization": "L0",
    "c3_kw_intent_mapper": "L0",
    "c4_serp_landscape": "L0",
    "c5_competitor_content": "L0",
    "c6_brand_loader": "L0",
    "c7_strategist": "L1",
    "c8_brief_compiler": "L1",
    "c9_outline": "L2",
    "c10_hook": "L3",
    "c11_section_drafter": "L3",
    "c12_faq": "L3",
    "c13_evidence": "L4",
    "c14_eeat": "L4",
    "c15_media": "L4",
    "c16_editorial": "L5",
    "c17_a11y_perf": "L5",
    "c18_schema": "L5",
    "c19_critic": "L6",
    "c20_render_critic": "L6",
    "c21_comparison_judge": "L6",
    "c22_packager": "L7",
}

# layer -> entry node to route back to when a critic failure is owned by that layer
LAYER_ENTRY: dict[str, str] = {
    "L0": "c1_source_reconciler",
    "L1": "c7_strategist",
    "L2": "c9_outline",
    "L3": "c10_hook",
    "L4": "c13_evidence",
    "L5": "c16_editorial",
}

# Phase 1 walking-skeleton roster (BUILD-SPEC §11 Phase 1)
PHASE1_NODES = [
    "c0_intake_router", "c1_source_reconciler", "c7_strategist",
    "c8_brief_compiler", "c9_outline", "c10_hook", "c11_section_drafter",
    "c12_faq", "c13_evidence", "c16_editorial", "c18_schema",
    "c19_critic", "c22_packager",
]

# Full roster (Phase 4): execution order follows the layer sequence.
# Cold-only nodes (c3-c5) and rebuild-only nodes (c21) self-gate on state["mode"].
ALL_NODES = [
    "c0_intake_router", "c1_source_reconciler", "c2_cannibalization",
    "c3_kw_intent_mapper", "c4_serp_landscape", "c5_competitor_content",
    "c6_brand_loader",
    "c7_strategist", "c8_brief_compiler", "c9_outline",
    "c10_hook", "c11_section_drafter", "c12_faq",
    "c13_evidence", "c14_eeat", "c15_media",
    "c16_editorial", "c17_a11y_perf", "c18_schema",
    "c19_critic", "c20_render_critic", "c21_comparison_judge",
    "c22_packager",
]


def owning_layer(node_id: str) -> str:
    """Layer that owns a node; KeyError on unknown node ids (fail loud)."""
    return NODE_LAYER[node_id]


def apply_route_back(state: ContentState, layer: str, cap: int) -> ContentState:
    """Record a critic-triggered route-back to `layer`.

    Increments route_back_count[layer]; once the count would exceed `cap`,
    raises EscalateToHuman instead of looping again.
    """
    counts = state.setdefault("route_back_count", {})
    next_count = counts.get(layer, 0) + 1
    if next_count > cap:
        raise EscalateToHuman(layer, next_count, cap, failures=(state.get("critic_report") or {}).get("failures"))
    counts[layer] = next_count
    return state


def _load_node(node_id: str) -> Callable[[dict], dict]:
    module = importlib.import_module(f"nodes.content.{node_id}")
    return module.run


def _validated(node_id: str, fn: Callable[[dict], dict]) -> Callable[[dict], dict]:
    def wrapped(state: dict) -> dict:
        from time import perf_counter

        from llm import drain_usage

        drain_usage()  # discard anything stale from a failed prior node
        start = perf_counter()
        update = fn(state) or {}
        duration_ms = round((perf_counter() - start) * 1000, 1)
        validate_state({**state, **update}, after_node=node_id)
        usage = drain_usage()
        # accumulate a runlog entry (BUILD-SPEC §10: one section per node).
        # duration/cost are runlog-only — the packager's qa_checklist must stay
        # deterministic so resumed runs hash identically (Phase 5 acceptance).
        entry = {
            "node": node_id,
            "output_keys": sorted(k for k in update if not k.startswith("_")),
            "guardrails": update.get("_guardrails", []),
            "duration_ms": duration_ms,
            "usage": usage,
            "cost_usd": round(sum(u["cost_usd"] for u in usage), 6),
        }
        runlog = list(state.get("_runlog", []))
        runlog.append(entry)
        update["_runlog"] = runlog
        return update
    wrapped.__name__ = node_id
    return wrapped


def _route_back_cap() -> int:
    import yaml
    from pathlib import Path
    return yaml.safe_load((Path(__file__).parent.parent / "config.yaml").read_text())["route_back_cap"]


def critic_gate(state: dict) -> str:
    """L6 gate: combine c19/c20/c21 verdicts. Any blocker failure routes back
    to the owning layer (capped → EscalateToHuman); otherwise package."""
    failures: list[dict] = []
    for key in ("critic_report", "render_report", "comparison_report"):
        report = state.get(key) or {}
        if report.get("verdict") == "fail":
            failures += [f for f in report.get("failures", [])
                         if f.get("severity") == "blocker"]
    if not failures:
        return "c22_packager"
    layer = owning_layer(failures[0]["owning_step"])
    apply_route_back(state, layer, _route_back_cap())
    return LAYER_ENTRY[layer]


def build_content_graph(checkpointer=None, nodes: list[str] | None = None):
    """Build the LangGraph StateGraph for Pipeline B.

    `nodes` defaults to the full roster. Raises NotImplementedError listing any
    node modules that don't exist yet — never wires a silent no-op.
    """
    from langgraph.graph import END, START, StateGraph

    roster = nodes or ALL_NODES
    missing = []
    impls: dict[str, Callable] = {}
    for node_id in roster:
        try:
            impls[node_id] = _validated(node_id, _load_node(node_id))
        except ModuleNotFoundError:
            missing.append(node_id)
    if missing:
        raise NotImplementedError(
            f"Content nodes not yet implemented (build them in their phase): {missing}"
        )

    g = StateGraph(ContentState)
    for node_id, fn in impls.items():
        g.add_node(node_id, fn)

    # Linear-with-gate wiring in layer order; the L6 gate sits after the last
    # critic in the roster. (True parallel fan-outs are a Phase 5 optimization —
    # node ownership of disjoint keys already makes them safe.)
    order = [n for n in roster if n in impls]
    last_critic = next((n for n in reversed(order)
                        if n in ("c21_comparison_judge", "c20_render_critic", "c19_critic")),
                       None)
    g.add_edge(START, order[0])
    for a, b in zip(order, order[1:]):
        if a == last_critic:
            continue  # gate decides the exit edge
        g.add_edge(a, b)
    if last_critic:
        g.add_conditional_edges(last_critic, critic_gate)
    g.add_edge("c22_packager", END)

    return g.compile(checkpointer=checkpointer)
