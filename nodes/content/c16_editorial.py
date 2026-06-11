"""c16_editorial (L5): merge lead + sections + FAQ into one draft.

Deterministic concatenation in outline order so the "introduce NO new facts"
rule holds by construction; the token-level new-number check is asserted anyway.
"""
from __future__ import annotations

from ledger import FactsLedger, extract_numbers


def run(state: dict) -> dict:
    outline = state.get("outline") or {}
    sections = state.get("sections") or {}
    order = [s["id"] for s in outline.get("sections", [])] or list(sections)

    parts = [state.get("lead", "").strip()]
    for sid in order:
        if sections.get(sid):
            parts.append(sections[sid].strip())
    faq = state.get("faq") or []
    if faq:
        parts.append("## Frequently asked questions")
        for item in faq:
            parts.append(f"### {item.get('q', '')}\n\n{item.get('a', '')}".strip())
    draft = "\n\n".join(p for p in parts if p)

    led = FactsLedger(list(state.get("facts_ledger", [])))
    source_numbers: set[float] = set(led.verified_numbers())
    for p in parts:
        source_numbers |= extract_numbers(p)
    new_numbers = sorted(extract_numbers(draft) - source_numbers)

    return {
        "draft": draft,
        "_guardrails": [{"check": "no_new_facts", "new_numbers": new_numbers,
                         "ok": not new_numbers}],
    }
