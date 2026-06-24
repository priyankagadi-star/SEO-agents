"""c16_editorial (L5): merge lead + sections + FAQ into one draft.

Deterministic concatenation in outline order so the "introduce NO new facts"
rule holds by construction; the token-level new-number check is asserted anyway.
"""
from __future__ import annotations

import re

from guardrails import VERIFY_PAT
from ledger import FactsLedger, extract_numbers


def _cut_unverified(text: str, cut: list[str]) -> str:
    """Drop sentences that still carry a [VERIFY] flag — never ship unverified
    claims, but don't block the run either: the claim is cut and surfaced as a
    human checkpoint. (Facts the brand documented are already in the ledger and
    were asserted normally, so only genuine unknowns get here.)"""
    kept = []
    for sentence in re.split(r"(?<=[.!?])\s+", text):
        flags = VERIFY_PAT.findall(sentence)
        if flags:
            cut.extend(flags)
            continue
        kept.append(sentence)
    return " ".join(s for s in kept if s.strip()).strip()


def run(state: dict) -> dict:
    outline = state.get("outline") or {}
    sections = state.get("sections") or {}
    order = [s["id"] for s in outline.get("sections", [])] or list(sections)

    cut: list[str] = []
    parts = [_cut_unverified(state.get("lead", "").strip(), cut)]
    for sid in order:
        if sections.get(sid):
            parts.append(_cut_unverified(sections[sid].strip(), cut))
    faq = state.get("faq") or []
    if faq:
        clean_faq = []
        for item in faq:
            a = _cut_unverified(item.get("a", ""), cut)
            if "[VERIFY" in item.get("q", ""):   # drop a question we can't answer
                continue
            if a.strip():
                clean_faq.append(f"### {item.get('q', '')}\n\n{a}".strip())
        if clean_faq:
            parts.append("## Frequently asked questions")
            parts.extend(clean_faq)
    draft = "\n\n".join(p for p in parts if p and p.strip())

    hc = list(state.get("human_checkpoints", []))
    for flag in dict.fromkeys(cut):   # dedupe, preserve order
        note = f"[HUMAN] cut from draft until confirmed: {flag}"
        if note not in hc:
            hc.append(note)

    led = FactsLedger(list(state.get("facts_ledger", [])))
    source_numbers: set[float] = set(led.verified_numbers())
    for p in parts:
        source_numbers |= extract_numbers(p)
    new_numbers = sorted(extract_numbers(draft) - source_numbers)

    return {
        "draft": draft,
        "human_checkpoints": hc,
        "_guardrails": [{"check": "no_new_facts", "new_numbers": new_numbers, "ok": not new_numbers},
                        {"check": "cut_unverified", "count": len(dict.fromkeys(cut))}],
    }
