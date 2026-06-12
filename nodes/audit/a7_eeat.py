"""a7_eeat: author, credentials, Person/Org schema, trust signals. Deterministic."""
from __future__ import annotations

import re


def _f(check, status, evidence, fix=""):
    return {"check": check, "status": status, "evidence": evidence, "fix": fix}


def run(state: dict) -> dict:
    p = state["page"]
    text = p["text"]
    findings = []

    byline = re.search(r"\b[Bb]y\s+([A-Z][a-z]+(?:\s+[A-Z][a-z]+){0,2})", text)
    findings.append(_f("author_byline", "pass" if byline else "fail",
                       f"byline: {byline.group(0) if byline else 'none found'}",
                       "Add a named author with credentials." if not byline else ""))

    def _types(block):
        if isinstance(block, dict):
            yield block.get("@type")
            for item in block.get("@graph", []):
                if isinstance(item, dict):
                    yield item.get("@type")

    types = {t for b in p["jsonld"] for t in _types(b) if t}
    has_person_org = bool(types & {"Person", "Organization"})
    findings.append(_f("person_org_schema", "pass" if has_person_org else "warn",
                       f"schema types: {sorted(types)}",
                       "Add Person/Organization schema for the author and publisher."
                       if not has_person_org else ""))

    trust_links = [l for l in p["links"] if l and re.search(r"about|contact|privacy", l, re.I)]
    findings.append(_f("trust_signals", "pass" if trust_links else "warn",
                       f"{len(trust_links)} about/contact/privacy links",
                       "Link to about/contact pages for trust." if not trust_links else ""))

    fails = sum(1 for f in findings if f["status"] == "fail")
    return {"eeat_findings": {"findings": findings,
                              "score_0_2": 2 if fails == 0 else (1 if fails == 1 else 0)}}
