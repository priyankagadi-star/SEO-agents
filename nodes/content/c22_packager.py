"""c22_packager (L7): assemble the deliverable. Adds nothing; arranges.

Unresolved [VERIFY]/[HUMAN] items are listed explicitly in human_checkpoints —
never dropped.
"""
from __future__ import annotations

from pathlib import Path

import yaml

_CFG = yaml.safe_load((Path(__file__).parents[2] / "config.yaml").read_text())
_H1 = _CFG["ui_limits"]["h1_chars"]
_META = _CFG["ui_limits"]["meta_chars"]


def _title_variants(brief: dict, keyword: str) -> list[str]:
    base = brief.get("title_direction") or keyword
    candidates = [
        base,
        f"{keyword.title()}: A Practical Guide",
        f"How to Improve {keyword.title()}",
    ]
    out: list[str] = []
    for c in candidates:
        c = c[:_H1].strip()
        if c and c not in out:
            out.append(c)
    while len(out) < 3:
        out.append((base + f" ({len(out)+1})")[:_H1])
    return out[:3]


def run(state: dict) -> dict:
    brief = state.get("brief") or {}
    draft = state.get("draft", "")
    runlog = state.get("_runlog", [])

    unresolved = list(state.get("verify_list") or [])
    human_checkpoints = list(state.get("human_checkpoints") or [])

    package_out = {
        "title_variants": _title_variants(brief, state["primary_keyword"]),
        "meta": (brief.get("meta_direction") or f"{state['primary_keyword']} — learn how it works.")[:_META],
        "full_copy": draft,
        "schema_jsonld": state.get("schema_jsonld", {}),
        "media_manifest": state.get("media_plan") or [],
        "internal_links": brief.get("internal_link_targets", []),
        "qa_checklist": [{"node": e["node"], "guardrails": e.get("guardrails", [])} for e in runlog],
        "human_checkpoints": human_checkpoints,
        "unresolved_verify": unresolved,
        "measurement_plan": {
            "primary_metric": (state.get("success_metric") or {}).get("metric", "AI-citation share"),
            "review_after": "4 weeks",
            "note": "Judge on AI-citation share where GSC CTR is structurally suppressed.",
        },
    }
    return {"package_out": package_out, "_guardrails": [{"check": "packaged", "ok": True}]}
