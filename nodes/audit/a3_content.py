"""a3_content: answer-first, depth, freshness, readability. Deterministic
heuristics; Information-Gain hypotheses require a model and are deferred
honestly rather than fabricated."""
from __future__ import annotations

import re
from datetime import datetime, timezone


def _f(check, status, evidence, fix=""):
    return {"check": check, "status": status, "evidence": evidence, "fix": fix}


def run(state: dict) -> dict:
    p = state["page"]
    query = state.get("primary_query", "")
    text = p["text"]
    findings = []

    lead = " ".join(text.split()[:60]).lower()
    terms = [t for t in query.lower().split() if len(t) > 2]
    hit = sum(1 for t in terms if t in lead)
    answer_first = bool(terms) and hit / len(terms) >= 0.5
    findings.append(_f("answer_first", "pass" if answer_first else "fail",
                       f"{hit}/{len(terms)} query terms in first 60 words",
                       "Open with a 40-60 word direct answer to the query."
                       if not answer_first else ""))

    wc = p["word_count"]
    findings.append(_f("depth", "pass" if wc >= 600 else ("warn" if wc >= 300 else "fail"),
                       f"{wc} words",
                       "Expand coverage — thin pages rarely earn AI citations." if wc < 600 else ""))

    year = datetime.now(timezone.utc).year
    fresh = bool(re.search(rf"\b({year}|{year - 1})\b", text))
    findings.append(_f("freshness", "pass" if fresh else "warn",
                       f"recent year mention: {fresh}",
                       "Add/refresh dated evidence so engines can trust recency." if not fresh else ""))

    sentences = [s for s in re.split(r"[.!?]+\s", text) if s.strip()]
    avg_len = (sum(len(s.split()) for s in sentences) / len(sentences)) if sentences else 0
    findings.append(_f("readability", "pass" if avg_len <= 28 else "warn",
                       f"avg sentence length {avg_len:.0f} words",
                       "Shorten sentences (target ≤25 words avg)." if avg_len > 28 else ""))

    fails = sum(1 for f in findings if f["status"] == "fail")
    return {"content_findings": {
        "findings": findings,
        "information_gain_hypotheses": [],
        "information_gain_note": "hypotheses require a model pass — deferred, not fabricated",
        "score_0_2": 2 if fails == 0 else (1 if fails == 1 else 0),
    }}
