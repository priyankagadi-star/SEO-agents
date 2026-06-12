"""a2_onpage: title/meta lengths, H1 count, hierarchy, keyword coverage,
internal links. Deterministic."""
from __future__ import annotations

from urllib.parse import urljoin, urlparse


def _f(check, status, evidence, fix=""):
    return {"check": check, "status": status, "evidence": evidence, "fix": fix}


def run(state: dict) -> dict:
    p = state["page"]
    query = state.get("primary_query", "")
    findings = []

    title = p.get("title") or ""
    findings.append(_f("title_length", "pass" if 0 < len(title) <= 60 else "fail",
                       f"{len(title)} chars: {title[:80]!r}",
                       "Keep the title ≤60 chars." if len(title) > 60 else ("Add a title." if not title else "")))

    meta = p.get("meta_description") or ""
    findings.append(_f("meta_length", "pass" if 0 < len(meta) <= 155 else "fail",
                       f"{len(meta)} chars", "Write a meta description ≤155 chars."
                       if not (0 < len(meta) <= 155) else ""))

    h1s = [t for lvl, t in p["headings"] if lvl == 1]
    findings.append(_f("h1_count", "pass" if len(h1s) == 1 else "fail",
                       f"{len(h1s)} H1s: {h1s[:2]}", "Exactly one H1."
                       if len(h1s) != 1 else ""))

    levels = [lvl for lvl, _ in p["headings"]]
    skips = [(a, b) for a, b in zip(levels, levels[1:]) if b - a > 1]
    findings.append(_f("heading_hierarchy", "pass" if not skips else "warn",
                       f"level skips: {skips}" if skips else "no skipped levels",
                       "Do not skip heading levels." if skips else ""))

    terms = [t for t in query.lower().split() if len(t) > 2]
    surface = " ".join([title] + h1s).lower()
    covered = sum(1 for t in terms if t in surface)
    cov = covered / len(terms) if terms else 1.0
    findings.append(_f("keyword_coverage", "pass" if cov >= 0.6 else "fail",
                       f"{covered}/{len(terms)} query terms in title+H1 for {query!r}",
                       "Work the primary query into the title and H1." if cov < 0.6 else ""))

    host = urlparse(p["url"]).netloc
    internal = [l for l in p["links"]
                if l and urlparse(urljoin(p["url"], l)).netloc == host
                and not l.startswith("#")]
    findings.append(_f("internal_links", "pass" if len(internal) >= 4 else "warn",
                       f"{len(internal)} internal links",
                       "Add ≥4 contextual internal links." if len(internal) < 4 else ""))

    fails = sum(1 for f in findings if f["status"] == "fail")
    return {"onpage_findings": {"findings": findings,
                                "score_0_2": 2 if fails == 0 else (1 if fails <= 1 else 0)}}
