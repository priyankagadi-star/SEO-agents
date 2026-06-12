"""a4_geo: schema validity, citable chunks, FAQ readiness. Deterministic."""
from __future__ import annotations

import re

from tools.validators import validate_jsonld


def _f(check, status, evidence, fix=""):
    return {"check": check, "status": status, "evidence": evidence, "fix": fix}


def run(state: dict) -> dict:
    p = state["page"]
    findings = []

    jl = validate_jsonld(p["html"])
    types = sorted({b.get("@type") for b in jl["blocks"] if isinstance(b.get("@type"), str)})
    findings.append(_f("schema_present_valid",
                       "pass" if jl["count"] and jl["valid"] else ("warn" if jl["count"] else "fail"),
                       f"{jl['count']} blocks, types {types}, errors {jl['errors']}",
                       "Add valid JSON-LD (WebPage + FAQPage at minimum)." if not jl["count"] else
                       ("Fix schema errors." if not jl["valid"] else "")))

    # citable chunks: self-contained 40-80 word paragraphs an engine can quote
    paras = [pp.strip() for pp in re.split(r"\n{2,}", p["html"] and p["text"]) if pp.strip()]
    chunks = [pp for pp in paras if 40 <= len(pp.split()) <= 80]
    findings.append(_f("citable_chunks", "pass" if len(chunks) >= 3 else "warn",
                       f"{len(chunks)} quotable 40-80 word passages",
                       "Restructure key claims into self-contained 40-80 word passages."
                       if len(chunks) < 3 else ""))

    has_faq_schema = "FAQPage" in types
    has_faq_heading = any(re.search(r"\bfaq|frequently asked", t, re.I) for _, t in p["headings"])
    findings.append(_f("faq_readiness",
                       "pass" if (has_faq_schema and has_faq_heading) else
                       ("warn" if has_faq_heading else "fail"),
                       f"faq heading: {has_faq_heading}, FAQPage schema: {has_faq_schema}",
                       "Add a PAA-sourced FAQ block with matching FAQPage schema."
                       if not has_faq_heading else ("Add FAQPage schema matching the visible FAQ."
                                                    if not has_faq_schema else "")))

    fails = sum(1 for f in findings if f["status"] == "fail")
    return {"geo_findings": {"findings": findings, "schema_types": types,
                             "citable_chunk_count": len(chunks),
                             "score_0_2": 2 if fails == 0 else (1 if fails == 1 else 0)}}
