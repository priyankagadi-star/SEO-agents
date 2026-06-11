"""Pipeline A wiring — audit graph (BUILD-SPEC §5a).

Topology: a0 → [a1..a9 parallel] + a10 (parallel, needs only gsc) → a11.
Each node returns only the keys it owns, so the parallel fan-out merges safely.
Node modules are implemented in Phase 3; the topology is fixed here in Phase 0.
"""
from __future__ import annotations

import importlib
from typing import Callable

from state import AuditState, validate_state

AUDIT_NODES = [
    "a0_intake",
    "a1_technical", "a2_onpage", "a3_content", "a4_geo", "a5_serp",
    "a6_authority", "a7_eeat", "a8_ux", "a9_a11y_perf", "a10_analytics",
    "a11_synthesis",
]

PARALLEL_ANALYZERS = AUDIT_NODES[1:11]  # a1..a10 fan out after a0


def _load_node(node_id: str) -> Callable[[dict], dict]:
    module = importlib.import_module(f"nodes.audit.{node_id}")
    return module.run


def _validated(node_id: str, fn: Callable[[dict], dict]) -> Callable[[dict], dict]:
    def wrapped(state: dict) -> dict:
        update = fn(state)
        validate_state({**state, **update}, after_node=node_id)
        return update
    wrapped.__name__ = node_id
    return wrapped


def build_audit_graph(checkpointer=None):
    """Build the LangGraph StateGraph for Pipeline A (Phase 3)."""
    from langgraph.graph import END, START, StateGraph

    missing, impls = [], {}
    for node_id in AUDIT_NODES:
        try:
            impls[node_id] = _validated(node_id, _load_node(node_id))
        except ModuleNotFoundError:
            missing.append(node_id)
    if missing:
        raise NotImplementedError(
            f"Audit nodes not yet implemented (Phase 3): {missing}"
        )

    g = StateGraph(AuditState)
    for node_id, fn in impls.items():
        g.add_node(node_id, fn)
    g.add_edge(START, "a0_intake")
    for analyzer in PARALLEL_ANALYZERS:
        g.add_edge("a0_intake", analyzer)
        g.add_edge(analyzer, "a11_synthesis")
    g.add_edge("a11_synthesis", END)
    return g.compile(checkpointer=checkpointer)
