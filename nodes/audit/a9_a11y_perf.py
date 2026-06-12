"""a9_a11y_perf: alt coverage, heading order, base64 images, page weight,
hero lazy-load. Deterministic via tools/validators."""
from __future__ import annotations

from tools.validators import image_seo_audit


def _f(check, status, evidence, fix=""):
    return {"check": check, "status": status, "evidence": evidence, "fix": fix}


def run(state: dict) -> dict:
    p = state["page"]
    findings = []

    audit = image_seo_audit(p["html"])
    findings.append(_f("alt_coverage", "pass" if audit["alt_coverage"] == 1.0 else "fail",
                       f"{audit['alt_coverage']:.0%} of {audit['total']} images",
                       "Every image needs descriptive alt text." if audit["alt_coverage"] < 1 else ""))
    findings.append(_f("base64_images", "fail" if audit["base64_count"] else "pass",
                       f"{audit['base64_count']} data-URI images",
                       "Serve images as files, never base64." if audit["base64_count"] else ""))
    findings.append(_f("hero_loading", "fail" if audit["hero_lazy_loaded"] else "pass",
                       f"hero lazy-loaded: {audit['hero_lazy_loaded']}",
                       "Hero image must be eager with fetchpriority=high."
                       if audit["hero_lazy_loaded"] else ""))

    levels = [lvl for lvl, _ in p["headings"]]
    skips = [(a, b) for a, b in zip(levels, levels[1:]) if b - a > 1]
    findings.append(_f("heading_order", "pass" if not skips else "warn",
                       f"skips: {skips or 'none'}",
                       "Fix skipped heading levels." if skips else ""))

    weight_kb = len(p["html"].encode()) // 1024
    findings.append(_f("page_weight", "pass" if weight_kb <= 500 else "warn",
                       f"~{weight_kb} KB HTML",
                       "Reduce page weight (target ≤500KB HTML)." if weight_kb > 500 else ""))

    fails = sum(1 for f in findings if f["status"] == "fail")
    return {"a11y_findings": {"findings": findings, "image_audit": audit,
                              "score_0_2": 2 if fails == 0 else (1 if fails == 1 else 0)}}
