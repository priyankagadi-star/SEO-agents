"""Deterministic guardrails (BUILD-SPEC §6). NO model calls inside.

These functions are the product. Pure string/regex/number analysis; every
behavior is pinned by tests/test_guardrails.py.
"""
from __future__ import annotations

import re
from collections import Counter
from dataclasses import dataclass, field

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


# ---------------------------------------------------------------------------
# Intent governance (architecture v2) — deterministic, no model calls
# ---------------------------------------------------------------------------

_INTENT_STOP = {"the", "and", "for", "with", "your", "you", "a", "an", "to",
                "of", "in", "on", "is", "are", "how", "what", "why", "do"}

_TRANSACTIONAL = re.compile(
    r"\b(buy|purchase|pricing|price|prices|cost|costs|cheap|deal|deals|coupon|"
    r"discount|order|free\s+trial|trial|sign\s?up|subscribe|demo|quote|for\s+sale|checkout)\b", re.I)
_COMMERCIAL = re.compile(
    r"\b(best|top\s+\d+|vs\.?|versus|reviews?|compare|comparisons?|alternatives?|"
    r"software|platforms?|tools?|trackers?|tracking|track|monitor|monitoring|"
    r"services?|solutions?|vendors?|providers?|apps?|near\s+me|how\s+to\s+choose)\b", re.I)
_NAVIGATIONAL = re.compile(
    r"\b(log\s?in|sign\s?in|dashboard|my\s+account|portal|download)\b", re.I)
_INFORMATIONAL = re.compile(
    r"\b(what\s+is|what\s+are|how\s+to|how\s+do|how\s+does|how\s+can|why|when|where|who|"
    r"guide|tutorial|definition|define|meaning|examples?|formula|ideas|tips|explained|"
    r"learn|understand)\b", re.I)
# a definitional opener betrays an explainer where a commercial page should sell
# a definitional opener betrays an explainer where a commercial page should sell.
# Matched against the opening words only (callers pass H1 + lead). Conceptual
# nouns only — "is the platform/tool/software" is commercial and never matches.
_DEFINITIONAL = re.compile(
    r"\b(what\s+(is|are)\b|(is|are)\s+(a|an|the)\s+"
    r"(practice|process|method|methods|technique|concept|term|way|approach|set\s+of)\b|"
    r"is\s+defined\s+as|refers\s+to|means\s+that)", re.I)


def classify_intent(query: str) -> str:
    """commercial | informational | transactional | navigational (lexical).

    The load-bearing new function. Precedence: transactional → commercial →
    navigational → informational, defaulting to informational. Commercial
    outranks informational so 'how to choose a monitoring tool' is commercial,
    while 'what is X' (no product noun) stays informational.
    """
    q = (query or "").lower().strip()
    if _TRANSACTIONAL.search(q):
        return "transactional"
    if _COMMERCIAL.search(q):
        return "commercial"
    if _NAVIGATIONAL.search(q):
        return "navigational"
    if _INFORMATIONAL.search(q):
        return "informational"
    return "informational"


# page_type -> the intent types it is allowed to own (everything else delegates)
OWNED_INTENT_TYPES = {
    "feature": {"commercial", "transactional"},
    "landing": {"commercial", "transactional"},
    "listicle": {"commercial", "transactional"},
    "blog-listicle": {"commercial", "transactional"},
    "comparison": {"commercial", "transactional"},
    "guide": {"informational"},
    "glossary": {"informational"},
}


def owned_intent_types(page_type: str) -> set[str]:
    return OWNED_INTENT_TYPES.get(page_type, {"commercial", "transactional"})


def _terms(s: str) -> set[str]:
    return {w for w in re.sub(r"[^a-z0-9 ]", " ", (s or "").lower()).split()
            if len(w) > 3 and w not in _INTENT_STOP}


def mirror_score(copy: str, head_queries) -> float:
    """Fraction of commercial/transactional head queries whose key terms the
    copy mirrors (≥60% of a query's significant terms present ⇒ mirrored).
    No commercial queries ⇒ 1.0 (nothing to mirror)."""
    norm = (copy or "").lower()
    targets = []
    for q in head_queries or []:
        term = q.get("term") if isinstance(q, dict) else q
        it = q.get("intent_type") if isinstance(q, dict) else None
        if it in (None, "commercial", "transactional"):
            targets.append(term or "")
    if not targets:
        return 1.0
    mirrored = 0
    for term in targets:
        t = _terms(term)
        if not t:
            continue
        hit = sum(1 for w in t if re.search(rf"\b{re.escape(w)}\b", norm))
        if hit / len(t) >= 0.6:
            mirrored += 1
    return round(mirrored / len(targets), 3)


def _first_h1(draft: str, fallback_h1: str | None) -> str:
    if fallback_h1:
        return fallback_h1
    for line in (draft or "").splitlines():
        m = re.match(r"#\s+(.*)", line.strip())
        if m:
            return m.group(1)
    return ""


def intent_fit_check(draft, intent_contract, h1=None, head_queries=None,
                     mirror_threshold: float = 0.6) -> list[Violation]:
    """The Intent-Fit gate (deterministic subset). Active only when the contract
    is governed (cluster_map and/or GSC supplied); ungoverned/single-page runs
    return [] so legacy behavior is unchanged.

    Asserts: (1) delivered intent matches an owned intent type; (3) copy mirrors
    ≥threshold of commercial head queries; (4) H1 carries the primary keyword;
    (5) every delegated class has an outbound link. (2) — no sibling-owned
    section — is intent_boundary_check, run separately at the same gate.
    """
    if not intent_contract or not intent_contract.get("governed"):
        return []
    out: list[Violation] = []
    owned = set(intent_contract.get("owned_intent_types", []))
    primary_kw = intent_contract.get("primary_keyword", "")

    # (4) H1 carries the primary commercial keyword
    h1_text = _first_h1(draft, h1)
    kw_terms = _terms(primary_kw)
    if kw_terms and h1_text:
        present = sum(1 for w in kw_terms if re.search(rf"\b{re.escape(w)}\b", h1_text.lower()))
        if present / len(kw_terms) < 0.5:
            out.append(Violation("h1_missing_keyword",
                                 f"H1 {h1_text!r} does not carry the primary keyword {primary_kw!r}",
                                 severity="blocker"))

    # (1) delivered intent: a commercial/transactional page must SELL, not open
    # with a definitional explainer (the session's off-intent failure). Detected
    # precisely via a definitional opener — re-classifying text full of product
    # nouns always reads 'commercial', so it can't catch the drift.
    if owned and owned <= {"commercial", "transactional"}:
        lead = " ".join((draft or "").split()[:60])
        opener = f"{h1_text} {lead}".strip()
        if _DEFINITIONAL.search(opener):
            out.append(Violation("intent_drift",
                                  f"commercial page opens by explaining a concept, not selling a capability: "
                                  f"…{opener[:80]}…", severity="blocker"))

    # (3) query mirroring
    hq = head_queries if head_queries is not None else intent_contract.get("head_queries")
    if hq:
        ms = mirror_score(draft, hq)
        if ms < mirror_threshold:
            out.append(Violation("low_mirror_score",
                                  f"copy mirrors only {ms:.0%} of commercial head queries "
                                  f"(need ≥{mirror_threshold:.0%}) — use the buyer's own vocabulary",
                                  severity="blocker"))

    # (5) every delegated class must be linked out
    for qclass, url in (intent_contract.get("delegated_query_classes") or {}).items():
        if url and url.rstrip("/") not in (draft or "").replace(")", " ").replace("(", " "):
            out.append(Violation("missing_delegated_link",
                                  f"delegated class '{qclass}' must link to its owner {url} — not found in copy",
                                  severity="blocker"))
    return out


# ---------------------------------------------------------------------------
# Content quality gates (closes the AI-smell gap surfaced in live runs)
# ---------------------------------------------------------------------------

# Phrases that scream "model-written" to both readers and AI-detection scorers.
# Sourced from documented patterns in Helpful Content audits + observed Siftly run.
AI_TELL_PAT = re.compile(
    r"\b(delve into|in today'?s\s+(?:world|landscape|era)|in the era of|"
    r"navigate(?:\s+the\s+complex)?|leverages?|unlock\s+the\s+power|"
    r"at the heart of|ever[\s-]evolving|seamless(?:ly)?|"
    r"strategic blind spot|flying blind|fundamentally|reshaping|"
    r"transforms?\s+\w+\s+into|game[\s-]changing|cutting[\s-]edge|"
    r"in conclusion|harnessing|paradigm shift|the world of|"
    r"a\s+(?:new|brave)\s+(?:world|era)|in this article|"
    r"operating without|stand[\s-]?out|robust\s+(?:solution|platform))\b", re.I)


def ai_tell_check(text: str, threshold: int = 4) -> list[Violation]:
    """Count common AI-tell phrases; >threshold ⇒ blocker (forces a rewrite)."""
    hits = [m.group(0).lower() for m in AI_TELL_PAT.finditer(text or "")]
    if not hits:
        return []
    counts = {}
    for h in hits:
        counts[h] = counts.get(h, 0) + 1
    sev = "blocker" if len(hits) > threshold else "major"
    return [Violation("ai_tells",
                      f"{len(hits)} AI-tell phrase(s) — {dict(sorted(counts.items(), key=lambda x: -x[1])[:5])}",
                      severity=sev)]


def anaphora_check(text: str, max_bigram: int = 3, max_unigram: int = 6) -> list[Violation]:
    """Sentence-opener repetition (AI-rhythm tell). Detects bigram openers
    repeated more than max_bigram times, and high-risk unigram openers
    ('you', 'we', 'our') above max_unigram."""
    sentences = [s.strip() for s in re.split(r"(?<=[.!?])\s+", text or "") if s.strip()]
    counts_bi: dict[str, int] = {}
    counts_uni = {"you": 0, "we": 0, "our": 0, "this": 0}
    for s in sentences:
        words = re.sub(r"^[#*\s]+", "", s).lower().split()
        if not words:
            continue
        if words[0] in counts_uni:
            counts_uni[words[0]] += 1
        if len(words) >= 2:
            bi = f"{words[0]} {words[1]}"
            counts_bi[bi] = counts_bi.get(bi, 0) + 1
    bad_bi = {k: v for k, v in counts_bi.items() if v > max_bigram}
    bad_uni = {k: v for k, v in counts_uni.items() if v > max_unigram}
    if not (bad_bi or bad_uni):
        return []
    detail = []
    if bad_bi:
        detail.append(f"bigrams: {dict(sorted(bad_bi.items(), key=lambda x: -x[1])[:3])}")
    if bad_uni:
        detail.append(f"unigrams: {bad_uni}")
    return [Violation("anaphora", "repeated sentence-openers — " + "; ".join(detail),
                      severity="major")]


# competitor brand names that count as a named comparison (extend per-domain via state if needed)
_NAMED_COMPETITORS = re.compile(
    r"\b(Profound|Otterly|Bluefish|Brand24|Mention|SemRush|Ahrefs|Moz|"
    r"BrightEdge|Conductor|Surfer|Frase|Clearscope|Jasper|Writesonic|"
    r"ChatGPT|Gemini|Perplexity|Claude|Google|Microsoft|HubSpot|"
    r"Salesforce|Search\s+Console|GA4|Analytics)\b", re.I)


def vague_comparative_check(text: str) -> list[Violation]:
    """'Most X tools / unlike others / traditional approaches' without a named
    competitor or (fact:…) reference nearby = vague claim. Blocks the typical
    'most AI visibility tools just track…' filler."""
    out = []
    pat = re.compile(r"\b(most|other|unlike|traditional)\s+"
                      r"(?:ai\s+)?(?:visibility\s+)?"
                      r"(tools?|platforms?|systems?|approaches?|solutions?|vendors?|services?)",
                      re.I)
    for m in pat.finditer(text or ""):
        window = (text or "")[max(0, m.start() - 80): m.end() + 140]
        if FACT_REF_PAT.search(window) or _NAMED_COMPETITORS.search(window):
            continue
        out.append(Violation("vague_comparative",
                             f"'{m.group(0)}' with no named competitor or fact ref: …{window.strip()[:90]}…",
                             severity="major"))
    return out


# ===========================================================================
# GOAL gate — Information-Gain Score (BUILD-SPEC: the measurable value of a
# page that earns Google traffic). Deterministic; no model calls. The critic
# (c19) computes this every run and, when enforce_information_gain is true,
# fails any page that scores < threshold OR misses a hard pre-condition.
# ===========================================================================

_STOP = set("the a an and or of to in for on with is are be by your you we our it "
            "that this as at from can will not no into out across over their they "
            "them its his her these those than then so if but more most other".split())
_URL = re.compile(r"https?://([a-z0-9.\-]+)", re.I)
_DOMAIN_NOISE = {"schema.org", "www.w3.org", "w3.org", "example.com"}
_EXAMPLE_MARKERS = re.compile(
    r"\b(for example|for instance|such as|e\.g\.|imagine|consider|say you|"
    r"when you|let's say|scenario|walkthrough|step \d|case study)\b", re.I)


@dataclass
class GoalReport:
    score: float
    passed: bool
    threshold: float
    metrics: dict = field(default_factory=dict)        # name -> {value, threshold, points, weight, ok}
    preconditions: dict = field(default_factory=dict)  # name -> {ok, detail}
    violations: list = field(default_factory=list)     # list[Violation]


def _domains(text: str, owner: set[str]) -> set[str]:
    return {d.lower() for d in _URL.findall(text or "")
            if d.lower() not in owner and d.lower() not in _DOMAIN_NOISE}


def _sentences(text: str) -> list[str]:
    return [s.strip() for s in re.split(r"(?<=[.!?])\s+", text or "") if len(s.split()) >= 4]


def _content_tokens(text: str) -> list[str]:
    # drop URLs first so link lists don't inflate density/repetition
    t = re.sub(r"https?://\S+", " ", text or "")
    t = re.sub(r"\(fact:[a-z0-9\-]+\)", " ", t, flags=re.I)
    return [w.lower() for w in re.findall(r"[A-Za-z0-9']+", t)]


def information_gain_score(
    draft: str,
    ledger,
    *,
    author: dict | None = None,
    serp_entities: list | None = None,
    paa_questions: list | None = None,
    faq: list | None = None,
    trend_signals: list | None = None,
    brand_names: list | None = None,
    owner_domains: list | None = None,
    citations: list | None = None,
    word_budget=None,
    threshold: float = 70.0,
    enforce: bool = True,
) -> GoalReport:
    """Composite 0–100 Information-Gain Score + hard pre-conditions.

    All inputs are owner/run data; nothing is fetched. Count thresholds scale
    with the page's word_budget midpoint vs the 1,500-word feature baseline.
    """
    text = draft or ""
    toks = _content_tokens(text)
    wc = max(1, len(toks))
    sents = _sentences(re.sub(r"https?://\S+", " ", text))
    owner = {d.lower() for d in (owner_domains or [])} | {"siftly.ai", "www.siftly.ai"}
    brands = [b for b in (brand_names or []) if b]

    # threshold scaling (count metrics only)
    mid = 1500
    if word_budget and isinstance(word_budget, (list, tuple)) and len(word_budget) == 2:
        mid = (word_budget[0] + word_budget[1]) / 2
    scale = max(0.6, mid / 1500.0)
    def st(n):  # scaled count threshold
        return max(1, round(n * scale))

    metrics: dict = {}

    def grade(key, value, thr, weight, *, ratio=None):
        frac = min(1.0, (value / thr) if thr else 0.0) if ratio is None else min(1.0, ratio)
        pts = round(weight * frac, 1)
        metrics[key] = {"value": value, "threshold": thr, "weight": weight,
                        "points": pts, "ok": frac >= 1.0}
        return pts

    total = 0.0

    # 1. External authoritative citations (distinct non-owner domains) -------
    doms = _domains(text, owner)
    for c in (citations or []):
        for d in _URL.findall(c or ""):
            if d.lower() not in owner and d.lower() not in _DOMAIN_NOISE:
                doms.add(d.lower())
    # facts whose source is an external http URL also count as corroboration
    for fid in set(FACT_REF_PAT.findall(text)):
        f = ledger.get(fid) if hasattr(ledger, "get") else None
        su = (f or {}).get("source_url", "") if f else ""
        for d in _URL.findall(su or ""):
            if d.lower() not in owner and d.lower() not in _DOMAIN_NOISE:
                doms.add(d.lower())
    total += grade("external_citations", len(doms), 3, 18)

    # 2. Distinct sourced data points / statistics --------------------------
    sourced = set()
    for m in re.finditer(r"\d[\d,.]*\s*(?:%|x|×|#\d+|million|billion|engines|"
                         r"members|customers|months?|weeks?)?", text, re.I):
        frag = m.group(0).strip()
        if not re.search(r"\d", frag):
            continue
        span = text[max(0, m.start() - 90): m.end() + 90]
        if FACT_REF_PAT.search(span) or (hasattr(ledger, "supports_number")
                                         and ledger.supports_number(frag)):
            sourced.add(frag.lower())
    total += grade("sourced_data_points", len(sourced), st(5), 16)

    # 3. Original / proprietary data (owner benchmarks referenced in copy) ---
    proprietary = 0
    seen_p = set()
    facts = ledger.facts if hasattr(ledger, "facts") else (ledger if isinstance(ledger, list) else [])
    for f in facts:
        fid = f.get("id", "")
        if fid in seen_p:
            continue
        is_prop = fid.startswith("proof-") or fid.startswith("proprietary") or \
            f.get("source_url") in ("study", "benchmark", "internal-data")
        if is_prop and (f"(fact:{fid})" in text or _value_in_text(f, text)):
            proprietary += 1
            seen_p.add(fid)
    total += grade("proprietary_data", proprietary, 2, 16)

    # 4. Concrete examples / walkthroughs / scenarios -----------------------
    examples = len(_EXAMPLE_MARKERS.findall(text))
    examples += sum(1 for f in facts if f.get("id", "").startswith("proof-")
                    and _value_in_text(f, text))
    total += grade("concrete_examples", examples, st(3), 12)

    # 5. Entity coverage vs live SERP entity set ----------------------------
    if serp_entities:
        ents = [str(e).lower() for e in serp_entities if str(e).strip()]
        covered = sum(1 for e in ents if e in text.lower())
        cov = covered / max(1, len(ents))
        total += grade("entity_coverage", round(cov * 100), 80, 10, ratio=cov / 0.8)
    else:
        metrics["entity_coverage"] = {"value": None, "threshold": 80, "weight": 10,
                                      "points": 0.0, "ok": False,
                                      "note": "no live SERP entity set — not assessed"}

    # 6. Real question coverage (answers actual PAA) ------------------------
    faq = faq or []
    if paa_questions:
        paa = [_norm_q(q) for q in paa_questions]
        fq = [_norm_q(x.get("q", "") if isinstance(x, dict) else x) for x in faq]
        answered = sum(1 for p in paa if any(_q_overlap(p, q) for q in fq))
        total += grade("question_coverage", answered, st(5), 8)
        metrics["question_coverage"]["verified_paa"] = True
    else:
        total += grade("question_coverage", len(faq), st(5), 8)
        metrics["question_coverage"]["verified_paa"] = False

    # 7. Repetition ceiling (graded). 3-gram repeats: 4 pts if ≤3×, half if ≤6×,
    # zero otherwise. Density of top non-stopword: 4 pts if ≤2.5%, then linear
    # decay so a page on a topic where the topic-word naturally hits ~5% (e.g.
    # an AI-search page using "ai" everywhere) still earns partial credit. Hard
    # floor at 6% density / 9× n-gram = the page is genuinely repetitive prose.
    grams = Counter(tuple(toks[i:i + 3]) for i in range(len(toks) - 2))
    worst = grams.most_common(1)[0] if grams else (None, 0)
    cw = [t for t in toks if t not in _STOP and len(t) > 1]
    dens = (Counter(cw).most_common(1)[0][1] / wc * 100) if cw else 0
    n3 = worst[1]
    ngram_pts = 4.0 if n3 <= 3 else (2.0 if n3 <= 6 else 0.0)
    if dens <= 2.5:
        dens_pts = 4.0
    elif dens >= 6.0:
        dens_pts = 0.0
    else:
        dens_pts = round(4.0 * (6.0 - dens) / 3.5, 2)   # linear 2.5%->4pts, 6.0%->0
    rep_pts = ngram_pts + dens_pts
    rep_ok = n3 <= 3 and dens <= 2.5
    metrics["repetition"] = {"value": f"3gram×{n3}, density {dens:.1f}%",
                             "threshold": "≤3×, ≤2.5% for full credit; partial credit through 6.0%",
                             "weight": 8, "points": rep_pts, "ok": rep_ok,
                             "worst_3gram": " ".join(worst[0]) if worst[0] else None}
    total += rep_pts

    # 8. Brand self-reference ratio (≤ 1 mention / 120 words) ---------------
    bm = sum(len(re.findall(rf"\b{re.escape(b)}\b", text, re.I)) for b in brands) if brands else 0
    ratio_words = wc / bm if bm else wc
    brand_ok = ratio_words >= 120
    metrics["brand_ratio"] = {"value": f"1 per {ratio_words:.0f}w ({bm} mentions)",
                              "threshold": "1 per 120w", "weight": 6,
                              "points": round(6 * min(1.0, ratio_words / 120), 1),
                              "ok": brand_ok}
    total += metrics["brand_ratio"]["points"]

    # 9. Author E-E-A-T completeness ---------------------------------------
    a = author or {}
    have = [bool(a.get("name")), bool(a.get("credentials")),
            bool(a.get("bio")), bool(a.get("linkedin") or a.get("link") or a.get("sameAs"))]
    total += grade("author_eeat", sum(have), 4, 6)

    score = round(total, 1)

    # ---- hard pre-conditions (any miss = blocker, independent of score) ----
    pre: dict = {}
    val = sum(1 for s in sents if _carries_value(s))
    dvd = val / max(1, len(sents))
    pre["distinct_value_density"] = {"ok": dvd >= 0.60,
                                     "detail": f"{val}/{len(sents)} = {dvd*100:.0f}% carry a fact/example (need ≥60%)"}
    verify_n = len(VERIFY_PAT.findall(text))
    pre["no_unresolved_verify"] = {"ok": verify_n == 0,
                                   "detail": f"{verify_n} unresolved [VERIFY] in shipped copy"}
    sourced_trend = any(_URL.search(str(t)) or "(source" in str(t).lower()
                        or "according to" in str(t).lower() for t in (trend_signals or []))
    pre["freshness_sourced_trend"] = {"ok": sourced_trend,
                                      "detail": "≥1 current trend signal with a source"
                                                if sourced_trend else "no sourced trend signal (trends are owner-asserted, no URL)"}

    violations: list = []
    sev = "blocker" if enforce else "major"
    for name, p in pre.items():
        if not p["ok"]:
            violations.append(Violation(f"goal_precondition:{name}", p["detail"], severity=sev))
    if score < threshold:
        weak = sorted([(m, d) for m, d in metrics.items() if not d.get("ok")],
                      key=lambda kv: kv[1]["weight"] - kv[1]["points"], reverse=True)
        worst3 = ", ".join(f"{m} {d['points']}/{d['weight']}" for m, d in weak[:3])
        violations.append(Violation("goal_information_gain",
                                    f"Information-Gain Score {score}/100 < {threshold}. "
                                    f"Biggest gaps: {worst3}.", severity=sev))

    passed = score >= threshold and all(p["ok"] for p in pre.values())
    return GoalReport(score=score, passed=passed, threshold=threshold,
                      metrics=metrics, preconditions=pre, violations=violations)


def _value_in_text(fact: dict, text: str) -> bool:
    """A proprietary fact counts as 'used' if a salient token of its value appears."""
    val = str(fact.get("value", ""))
    # salient = capitalized names or numbers in the fact value
    for tok in re.findall(r"\b[A-Z][A-Za-z]{2,}\b|#?\d+(?:\.\d+)?x?", val):
        if len(tok) >= 3 and tok.lower() in text.lower():
            return True
    return False


def _norm_q(q: str) -> set:
    return {w for w in re.findall(r"[a-z]+", (q or "").lower()) if w not in _STOP and len(w) > 2}


def _q_overlap(a: set, b: set) -> bool:
    return bool(a and b and len(a & b) / max(1, min(len(a), len(b))) >= 0.5)


_VALUE_SIGNAL = re.compile(
    r"\d|#\d|%|\bvs\b|\bthan\b|\bunlike\b|—|"
    r"\(fact:[a-z0-9\-]+\)|"                       # cites a verified fact => grounded claim
    r"\bfor example\b|\bsuch as\b|\blike when\b|\bfor instance\b", re.I)
# a multi-word proper noun ("Search Engine Land", "Google AI Overviews") names a
# specific entity/source => information-bearing. Two+ consecutive Capitalized words,
# not counting a single leading capital (sentence start).
_PROPER_NOUN = re.compile(r"\b[A-Z][a-zA-Z]+\s+[A-Z][a-zA-Z]+(?:\s+[A-Z][a-zA-Z]+)*")


def _carries_value(sentence: str) -> bool:
    """A sentence carries distinct value if it states a number/percentage,
    cites a verified fact, names a specific entity/source, gives an example, or
    draws a comparison — not a bare restatement/transition."""
    s = sentence or ""
    if _VALUE_SIGNAL.search(s):
        return True
    # drop the first token so a sentence-initial capital alone doesn't count;
    # a real proper noun ("Search Engine Land") still has 2+ caps after that.
    rest = s.split(" ", 1)[1] if " " in s else ""
    return bool(_PROPER_NOUN.search(rest))
