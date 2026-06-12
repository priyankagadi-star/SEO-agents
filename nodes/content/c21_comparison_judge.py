"""c21_comparison_judge (L6, rebuild only): new draft vs the live page.

Skipped in cold mode (no live page to compare). Deterministic where the
check is mechanical: entity keep-list items must be present (blocker if not);
quality keep-list phrases from the audit need a rendered-page re-audit and are
reported honestly as not-machine-checkable here rather than rubber-stamped.
"""
from __future__ import annotations

import re


def run(state: dict) -> dict:
    if state["mode"] != "rebuild":
        return {"comparison_report": {"verdict": "skipped",
                                      "note": "cold mode — no live page to compare"}}

    draft = state.get("draft", "")
    lead = state.get("lead", "")
    failures, keep_audit = [], []

    for item in state.get("keep_list") or []:
        s = str(item)
        token = s.split(" differentiator")[0].strip()
        entity_like = bool(re.search(r"\b[A-Z][a-z]+", s))
        if entity_like:
            present = token.lower() in draft.lower()
            keep_audit.append({"item": s, "present": present,
                               "quote": token if present else None})
            if not present:
                failures.append({"description": f"rebuild dropped keep_list item: {s}",
                                 "owning_step": "c9_outline", "severity": "blocker",
                                 "evidence": s,
                                 "fix": "Cover this kept strength in the new draft."})
        else:
            keep_audit.append({"item": s, "present": None,
                               "note": "quality phrase — verify by re-auditing the rendered page (Pipeline A)"})

    lead_words = len(lead.split())
    if not 40 <= lead_words <= 60:
        failures.append({"description": f"answer-first lead is {lead_words} words (target 40-60)",
                         "owning_step": "c10_hook", "severity": "major",
                         "evidence": lead[:120],
                         "fix": "Rewrite the lead to 40-60 words."})

    blockers = [x for x in failures if x["severity"] == "blocker"]
    return {"comparison_report": {
        "verdict": "fail" if blockers else "pass",
        "keep_list_audit": keep_audit,
        "scorecard_delta": "not-computed — requires re-running Pipeline A on the published page",
        "failures": failures,
    }, "_guardrails": [{"check": "comparison_judge",
                        "verdict": "fail" if blockers else "pass"}]}
