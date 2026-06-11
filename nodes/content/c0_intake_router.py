"""c0_intake_router (L0): validate run inputs; HALT on missing required inputs.

Deterministic — no model call. BUILD-SPEC §5b: HALT if canonical_sources empty
or (net_new and brand_assets empty) → HumanInputRequired.
"""
from __future__ import annotations

from state import HumanInputRequired


def run(state: dict) -> dict:
    if not state.get("canonical_sources"):
        raise HumanInputRequired(
            "canonical_sources",
            "At least one canonical source URL is required for both modes.",
        )
    if state["mode"] == "net_new" and not state.get("brand_assets"):
        raise HumanInputRequired(
            "brand_assets", "net_new mode requires brand_assets (differentiators, author, etc.)."
        )
    hc = list(state.get("human_checkpoints", []))
    if not state.get("research_dossier"):
        hc.append("[HUMAN] research_dossier is empty — supply research notes or confirm none exist.")
    return {
        "human_checkpoints": hc,
        "_guardrails": [{"check": "intake_required_inputs", "status": "pass"}],
    }
