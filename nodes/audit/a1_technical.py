"""a1_technical: canonical, robots, status, viewport. Deterministic."""
from __future__ import annotations


def _f(check, status, evidence, fix=""):
    return {"check": check, "status": status, "evidence": evidence, "fix": fix}


def run(state: dict) -> dict:
    p = state["page"]
    findings = []

    findings.append(_f("http_status", "pass" if p["status_code"] == 200 else "fail",
                       f"status {p['status_code']}",
                       "" if p["status_code"] == 200 else "Serve the page with HTTP 200."))

    canonical = p.get("canonical")
    if not canonical:
        findings.append(_f("canonical", "fail", "no canonical link tag",
                           "Add a self-referencing canonical."))
    elif canonical.rstrip("/") != p["url"].rstrip("/"):
        findings.append(_f("canonical", "warn", f"canonical points elsewhere: {canonical}",
                           "Confirm the canonical target is intentional."))
    else:
        findings.append(_f("canonical", "pass", f"self-referencing: {canonical}"))

    robots = (p.get("robots_meta") or "").lower()
    findings.append(_f("robots", "fail" if "noindex" in robots else "pass",
                       f"robots meta: {robots or '(absent — indexable)'}",
                       "Remove noindex if this page should rank." if "noindex" in robots else ""))

    findings.append(_f("mobile_viewport", "pass" if p.get("viewport") else "fail",
                       f"viewport: {p.get('viewport') or 'missing'}",
                       "" if p.get("viewport") else "Add a responsive viewport meta tag."))

    findings.append(_f("js_rendering", "warn", p["limitations"][0],
                       "Re-audit with JS rendering before trusting content checks on SPA pages."))

    fails = sum(1 for f in findings if f["status"] == "fail")
    return {"tech_findings": {"findings": findings,
                              "score_0_2": 2 if fails == 0 else (1 if fails == 1 else 0)}}
