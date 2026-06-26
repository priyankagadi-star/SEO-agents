"""c11_section_drafter (L3): fan-out one drafting task per outline section.

Each task sees only its section spec + ledger + voice. flag_dont_fill runs on
each body at exit; unsupported numbers without a [VERIFY] flag are reported and
enforced at c19.
"""
from __future__ import annotations

import json

from guardrails import flag_dont_fill
from ledger import FactsLedger
from llm import call_node


def run(state: dict) -> dict:
    led = FactsLedger(list(state.get("facts_ledger", [])))
    contract = state.get("intent_contract", {})
    must_mirror = [q["term"] for q in contract.get("head_queries", [])
                   if q.get("intent_type") in ("commercial", "transactional")]
    sections: dict[str, str] = {}
    covered: list[str] = []
    for sec in (state.get("outline") or {}).get("sections", []):
        res = call_node(
            "c11_section_drafter", "writer",
            section_spec=json.dumps(sec),
            brand_voice=json.dumps(state.get("brand_voice", {})),
            must_mirror=json.dumps(must_mirror),
            ledger_markdown=led.to_markdown(),
        )
        if not isinstance(res, dict):
            res = {}
        sid = res.get("section_id") or sec.get("id")
        body = res.get("body_md") or res.get("body") or res.get("content") or res.get("markdown") or ""
        sections[sid] = body
        covered += res.get("entities_covered", []) if isinstance(res.get("entities_covered"), list) else []

    violations = []
    for body in sections.values():
        violations += flag_dont_fill(body, led)
    return {
        "sections": sections,
        "_guardrails": [{"check": "flag_dont_fill", "sections": len(sections),
                         "violations": [v.detail for v in violations]}],
    }
