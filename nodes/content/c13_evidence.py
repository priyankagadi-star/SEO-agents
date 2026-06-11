"""c13_evidence (L4): the verifier (≠ writer).

Phase 1 scope: with no web-lookup tool wired, every [VERIFY:] flag is resolved
as 'keep-flagged' and surfaced as a human checkpoint — never silently dropped,
never fabricated. Web-lookup resolution lands in Phase 3 behind tools/.
"""
from __future__ import annotations

from guardrails import VERIFY_PAT


def run(state: dict) -> dict:
    texts = [state.get("lead", "")]
    texts += list((state.get("sections") or {}).values())
    texts += [f.get("a", "") for f in (state.get("faq") or [])]

    flags: list[str] = []
    for t in texts:
        flags += VERIFY_PAT.findall(t)

    hc = list(state.get("human_checkpoints", []))
    verdicts = []
    for flag in flags:
        verdicts.append({"flag": flag, "verdict": "keep-flagged",
                         "note": "no web-lookup tool in Phase 1; needs human or Phase 3 resolution"})
        hc.append(f"[HUMAN] Resolve evidence flag (no automated source yet): {flag}")

    return {
        "verify_list": flags,
        "human_checkpoints": hc,
        "_c13_verdicts": verdicts,
        "_guardrails": [{"check": "evidence", "unresolved_flags": len(flags)}],
    }
