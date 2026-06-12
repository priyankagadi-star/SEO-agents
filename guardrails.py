"""Deterministic guardrails (BUILD-SPEC §6). NO model calls inside.

These functions are the product. Pure string/regex/number analysis; every
behavior is pinned by tests/test_guardrails.py.
"""
from __future__ import annotations

import re
from dataclasses import dataclass

from ledger import extract_numbers, word_to_number


@dataclass
class Violation:
    kind: str
    detail: str
    severity: str = "blocker"


VERIFY_PAT = re.compile(r"\[VERIFY[^\]]*\]")
QUANTIFIERS = re.compile(r"\b(every|all|only|first|always|never|guaranteed)\b", re.I)
FACT_REF_PAT = re.compile(r"\(fact:([a-z0-9\-]+)\)")


def flag_dont_fill(text: str, ledger) -> list[Violation]:
    """A number/stat in text that maps to no verified Fact and carries no [VERIFY] flag is a violation."""
    out = []
    for m in re.finditer(r"(\d[\d,.]*\s*(?:%|million|billion|M|B|x|×)|\$\d[\d,.]*)", text):
        span = text[max(0, m.start() - 80): m.end() + 80]
        if VERIFY_PAT.search(span):            # flagged — OK
            continue
        if not ledger.supports_number(m.group(0)):
            out.append(Violation("unsourced_number", f"'{m.group(0)}' near: …{span.strip()[:90]}…"))
    return out


def grounding_check(claims: list[str], ledger) -> list[Violation]:
    """Every strategic claim must cite a ledger fact id like (fact:engines-count)."""
    out = []
    for c in claims:
        ids = FACT_REF_PAT.findall(c)
        if not ids:
            out.append(Violation("ungrounded_claim", c[:140]))
        for fid in ids:
            f = ledger.get(fid)
            if f is None or f["status"] != "verified":
                out.append(Violation("unverified_fact_ref", f"{fid} in: {c[:100]}"))
    return out


def _normalize(text: str) -> str:
    t = text.lower()
    # word-numbers -> digits so "four engines" matches "4 engines"
    for w in sorted(("zero one two three four five six seven eight nine ten "
                     "eleven twelve thirteen fourteen fifteen sixteen seventeen "
                     "eighteen nineteen twenty").split(), key=len, reverse=True):
        n = word_to_number(w)
        t = re.sub(rf"\b{w}\b", str(int(n)), t)  # type: ignore[arg-type]
    t = re.sub(r"[^\w\s$%.]", " ", t)
    return re.sub(r"\s+", " ", t).strip()


def canonical_verify(claim: str, fetched_sources: dict[str, str]) -> str:
    """Return 'verified' | 'unverified' | 'conflict'. fetched_sources = {url: page_text}.

    Deterministic: substring/normalized-number containment, no LLM. The CALLER
    (c1/c13) may use a model to extract candidate values, but the final
    containment check happens here.

    Logic: a source SUPPORTS the claim if the normalized claim is a substring of
    the normalized source, or every (number, context) pair in the claim appears
    in the source with the same number. A source CONTRADICTS if the claim's
    context appears with a different number. Any contradiction ⇒ 'conflict';
    support without contradiction ⇒ 'verified'; neither ⇒ 'unverified'.
    """
    norm_claim = _normalize(claim)
    # (number, up-to-3 following words) pairs from the claim
    pairs: list[tuple[float, str]] = []
    for m in re.finditer(r"(\d[\d,]*(?:\.\d+)?)\s+((?:[a-z][\w\-]*\s*){1,3})", norm_claim):
        num = float(m.group(1).replace(",", ""))
        ctx = m.group(2).strip()
        if ctx:
            pairs.append((num, ctx))

    supported = False
    contradicted = False
    for _url, page_text in fetched_sources.items():
        norm_src = _normalize(page_text)
        if norm_claim and norm_claim in norm_src:
            supported = True
            continue
        if not pairs:
            continue
        all_match = True
        any_context_hit = False
        for num, ctx in pairs:
            ctx_pat = re.escape(ctx).replace(r"\ ", r"\s+")
            hits = re.findall(rf"(\d[\d,]*(?:\.\d+)?)\s+{ctx_pat}", norm_src)
            if not hits:
                all_match = False
                continue
            any_context_hit = True
            nums = {float(h.replace(",", "")) for h in hits}
            if num in nums:
                continue
            all_match = False
            contradicted = True
        if pairs and all_match and any_context_hit:
            supported = True
    if contradicted:
        return "conflict"
    return "verified" if supported else "unverified"


def fact_diff(artifact_text: str, ledger) -> list[Violation]:
    """Any number/name in artifact contradicting a locked Fact value -> blocker.

    Per-fact matchers: each Fact may define a regex in 'claim_pattern' whose
    first capture group (digits or a word-number, e.g. 'nine') must normalize
    to a number present in the locked value.
    """
    out: list[Violation] = []
    for f in ledger.facts:
        pattern = f.get("claim_pattern")
        if not pattern:
            continue
        if f["status"] == "conflict":
            # a referenced conflicting fact is itself a blocker until resolved
            if re.search(pattern, artifact_text, re.I):
                out.append(Violation(
                    "conflicting_fact_referenced",
                    f"fact '{f['id']}' is in conflict ({f.get('conflict_values')}) and is referenced in artifact",
                ))
            continue
        locked_nums = extract_numbers(f["value"])
        if not locked_nums:
            continue
        for m in re.finditer(pattern, artifact_text, re.I):
            captured = m.group(1) if m.groups() else m.group(0)
            num = word_to_number(captured)
            if num is None:
                continue  # capture isn't a number ("the AI engines") — not a contradiction
            if num not in locked_nums:
                out.append(Violation(
                    "fact_contradiction",
                    f"artifact says '{m.group(0).strip()}' but fact '{f['id']}' locks value '{f['value']}'",
                ))
    return out


def quantifier_check(artifact_text: str, ledger) -> list[Violation]:
    """Every QUANTIFIERS hit must sit within 120 chars of a (fact:...) ref or a ledger-supported value."""
    out: list[Violation] = []
    for m in QUANTIFIERS.finditer(artifact_text):
        window = artifact_text[max(0, m.start() - 120): m.end() + 120]
        ref_ok = False
        for fid in FACT_REF_PAT.findall(window):
            f = ledger.get(fid)
            if f is not None and f["status"] == "verified":
                ref_ok = True
                break
        if ref_ok:
            continue
        if extract_numbers(window) & ledger.verified_numbers():
            continue
        out.append(Violation(
            "unsupported_quantifier",
            f"'{m.group(0)}' with no nearby (fact:…) ref or ledger-supported value: …{window.strip()[:90]}…",
            severity="major",
        ))
    return out


def source_precedence(conflict: dict, precedence: list[str]) -> dict:
    """NEVER auto-picks. Returns {'action': 'surface', 'options': [...], 'recommended': highest-precedence}.

    conflict = {"fact_id": str, "options": [{"value", "source_url", "source_class"}, ...]}
    """
    options = list(conflict.get("options", []))

    def rank(opt: dict) -> int:
        cls = opt.get("source_class", "")
        return precedence.index(cls) if cls in precedence else len(precedence)

    recommended = min(options, key=rank) if options else None
    return {
        "action": "surface",            # invariant: never 'resolve' / never auto-pick
        "fact_id": conflict.get("fact_id"),
        "options": options,
        "recommended": recommended,
        "note": "Conflict must be resolved by a human; 'recommended' is the highest-precedence source class only.",
    }


def intent_boundary_check(outline, cluster_map, page_intent=None, current_url=None) -> list[Violation]:
    """The cluster-level sibling of fact_diff: stop a page hosting a section
    whose intent is owned by a sibling URL ("link, don't host").

    Deterministic, no model calls. `cluster_map` may be a ClusterMap or the plain
    dict from state; a falsy cluster_map means single-page mode → no violations.
    A section is allowed when it covers the page's own intent (page_intent) or an
    intent this URL (current_url) owns; otherwise it is a blocker to delegate.
    """
    if not cluster_map:
        return []
    from cluster_map import ClusterMap
    cm = cluster_map if hasattr(cluster_map, "match") else ClusterMap.from_config(cluster_map)
    if cm is None:
        return []

    cur = (current_url or "").rstrip("/")
    out: list[Violation] = []
    for section in (outline or {}).get("sections", []):
        text = f"{section.get('h2', '')} {section.get('intent', '')}".strip()
        if not text:
            continue
        entry = cm.match(text)
        if entry is None:
            continue  # unowned intent — novel, fine to host
        if page_intent and entry.intent == page_intent:
            continue  # this is the page's own intent
        if cur and entry.url.rstrip("/") == cur:
            continue  # this URL already owns it
        label = section.get("h2") or section.get("id") or text[:40]
        out.append(Violation(
            "intent_trespass",
            f"section '{label}' covers intent '{entry.intent}' owned by {entry.url} — link, don't host",
        ))
    return out
