"""a6_authority: off-page signals. No API wired — emit "not-assessed"
honestly (BUILD-SPEC §5a) rather than estimating from model memory."""
from __future__ import annotations


def run(state: dict) -> dict:
    return {"authority_findings": {
        "status": "not-assessed",
        "note": "No backlink/brand-mention API configured; off-page authority "
                "was not assessed. Do not interpret this as a pass or fail.",
        "findings": [],
        "score_0_2": None,
    }}
