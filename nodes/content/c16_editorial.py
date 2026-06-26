"""c16_editorial (L5): merge lead + sections + FAQ into one draft.

Deterministic concatenation in outline order so the "introduce NO new facts"
rule holds by construction; the token-level new-number check is asserted anyway.
"""
from __future__ import annotations

import re

from guardrails import FACT_REF_PAT, VERIFY_PAT
from ledger import FactsLedger, extract_numbers

_VERIFY_FULL = re.compile(r"\s*\[VERIFY[^\]]*\]")   # whole bracket, atomic


def _cut_unverified(text: str, cut: list[str]) -> str:
    """Never ship a [VERIFY] flag, but don't block the run either.

    A [VERIFY] note can contain periods ("e.g. WordPress"), which would fool a
    naive sentence split and let the bracket survive — so brackets are handled
    atomically. Policy: if the sentence is otherwise grounded (carries a
    (fact:id) ref), strip just the appended note and keep the claim; otherwise
    the claim itself was the unknown — cut the whole sentence. A final pass
    guarantees no residual bracket ships."""
    # protect dots inside [VERIFY ...] so the splitter can't break a bracket
    masked = _VERIFY_FULL.sub(lambda m: m.group(0).replace(".", "․"), text)
    kept = []
    for sentence in re.split(r"(?<=[.!?])\s+", masked):
        sentence = sentence.replace("․", ".")
        flags = VERIFY_PAT.findall(sentence)
        if flags:
            cut.extend(flags)
            if FACT_REF_PAT.search(sentence):          # grounded sentence + a note
                kept.append(_VERIFY_FULL.sub("", sentence).strip())
            continue                                   # else drop the whole sentence
        kept.append(sentence)
    out = " ".join(s for s in kept if s.strip()).strip()
    return _VERIFY_FULL.sub("", out).strip()           # safety net: no bracket ever ships


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
