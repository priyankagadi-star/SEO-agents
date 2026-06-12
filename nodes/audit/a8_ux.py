"""a8_ux: CTA presence, demo/placeholder data detection, conversion path.
Deterministic."""
from __future__ import annotations

import re

_CTA_PAT = re.compile(
    r"\b(get started|start free|free trial|book a demo|request a demo|sign up|"
    r"try (?:it|now|free)|contact (?:us|sales)|subscribe|download)\b", re.I)
_PLACEHOLDER_PAT = re.compile(r"\b(acme|globex|lorem ipsum|lorem|john doe|example\.com)\b", re.I)


def _f(check, status, evidence, fix=""):
    return {"check": check, "status": status, "evidence": evidence, "fix": fix}


def run(state: dict) -> dict:
    p = state["page"]
    text = p["text"]
    findings = []

    ctas = sorted({m.group(0).lower() for m in _CTA_PAT.finditer(text)})
    findings.append(_f("cta_presence", "pass" if ctas else "fail",
                       f"CTAs found: {ctas or 'none'}",
                       "Add a clear primary CTA (≤5 words)." if not ctas else ""))

    placeholders = sorted({m.group(0) for m in _PLACEHOLDER_PAT.finditer(text)})
    findings.append(_f("placeholder_data", "fail" if placeholders else "pass",
                       f"placeholder/demo strings: {placeholders or 'none'}",
                       "Replace demo data with real product data." if placeholders else ""))

    early_cta = bool(_CTA_PAT.search(" ".join(text.split()[:250])))
    findings.append(_f("conversion_path", "pass" if early_cta else "warn",
                       f"CTA within first ~250 words: {early_cta}",
                       "Surface a CTA near the top of the page." if not early_cta else ""))

    fails = sum(1 for f in findings if f["status"] == "fail")
    return {"ux_findings": {"findings": findings, "ctas": ctas,
                            "placeholder_data_found": placeholders,
                            "score_0_2": 2 if fails == 0 else (1 if fails == 1 else 0)}}
