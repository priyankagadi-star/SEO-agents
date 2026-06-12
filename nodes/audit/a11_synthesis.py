"""a11_synthesis: merge all findings → scorecard, defects (each naming the
content node that owns the fix), root_causes, keep_list, the Diagnosis object,
and the master report. Deterministic merge — introduces no findings of its own.
"""
from __future__ import annotations

from state import validate_diagnosis

# audit check -> content node that owns the fix (the seam's routing table)
OWNER = {
    "answer_first": "c10_hook",
    "depth": "c11_section_drafter",
    "readability": "c11_section_drafter",
    "freshness": "c11_section_drafter",
    "citable_chunks": "c11_section_drafter",
    "placeholder_data": "c11_section_drafter",
    "faq_readiness": "c12_faq",
    "schema_present_valid": "c18_schema",
    "title_length": "c8_brief_compiler",
    "meta_length": "c8_brief_compiler",
    "h1_count": "c8_brief_compiler",
    "keyword_coverage": "c8_brief_compiler",
    "cta_presence": "c8_brief_compiler",
    "conversion_path": "c8_brief_compiler",
    "heading_hierarchy": "c9_outline",
    "heading_order": "c9_outline",
    "author_byline": "c14_eeat",
    "person_org_schema": "c14_eeat",
    "trust_signals": "c14_eeat",
    "alt_coverage": "c15_media",
    "base64_images": "c15_media",
    "hero_loading": "c15_media",
    "page_weight": "c17_a11y_perf",
    "internal_links": "c22_packager",
    # site-level items a content rebuild can only surface, not fix
    "http_status": "c22_packager",
    "canonical": "c22_packager",
    "robots": "c22_packager",
    "mobile_viewport": "c22_packager",
    "js_rendering": "c22_packager",
}

_BLOCKER_CHECKS = {"placeholder_data", "http_status", "robots"}

_KEEP_PHRASE = {
    "answer_first": "answer-first lead that addresses the query immediately",
    "canonical": "correct self-referencing canonical",
    "h1_count": "single clear H1",
    "title_length": "title within the 60-char limit",
    "meta_length": "meta description within the 155-char limit",
    "keyword_coverage": "primary query covered in title/H1",
    "schema_present_valid": "valid structured data already in place",
    "faq_readiness": "FAQ block with matching schema",
    "alt_coverage": "complete image alt coverage",
    "cta_presence": "clear calls to action",
    "citable_chunks": "AI-quotable self-contained passages",
    "author_byline": "named author byline",
    "freshness": "fresh, dated evidence",
}

_AREAS = [
    ("technical", "tech_findings"), ("onpage", "onpage_findings"),
    ("content", "content_findings"), ("geo", "geo_findings"),
    ("serp", "serp_findings"), ("authority", "authority_findings"),
    ("eeat", "eeat_findings"), ("ux", "ux_findings"),
    ("a11y_perf", "a11y_findings"),
]


def run(state: dict) -> dict:
    scorecard: dict[str, int] = {}
    defects: list[dict] = []
    keep_list: list[str] = []

    for area, key in _AREAS:
        block = state.get(key) or {}
        score = block.get("score_0_2")
        if isinstance(score, int):
            scorecard[area] = score
        for f in block.get("findings", []):
            check, status = f["check"], f["status"]
            if status == "pass":
                if check in _KEEP_PHRASE:
                    keep_list.append(_KEEP_PHRASE[check])
            else:
                severity = ("blocker" if (status == "fail" and check in _BLOCKER_CHECKS)
                            else "major" if status == "fail" else "minor")
                defects.append({
                    "description": f"[{area}/{check}] {f['evidence']}",
                    "owning_step": OWNER.get(check, "c22_packager"),
                    "severity": severity,
                    "fix": f.get("fix") or "See evidence.",
                })

    perf = state.get("performance") or {}
    root_causes = []
    zero_areas = [a for a, s in scorecard.items() if s == 0]
    if zero_areas:
        root_causes.append(f"systemic weakness in: {', '.join(zero_areas)}")
    if any(d["owning_step"] == "c10_hook" for d in defects):
        root_causes.append("no extractable direct answer — engines have nothing clean to cite")
    if any(d["owning_step"] in ("c12_faq", "c18_schema") for d in defects):
        root_causes.append("missing FAQ/schema reduces eligibility for AI-Overview citations")
    if perf.get("aio_flag"):
        root_causes.append("rankings exist but clicks are consumed inside AI answers "
                           "(zero-click suppression) — optimize for citation share")
    if not root_causes:
        root_causes.append("no systemic root cause — defects are isolated; fix individually")

    diagnosis = {
        "url": state["url"],
        "page_type": state.get("page_type", "feature"),
        "primary_query": state.get("primary_query", ""),
        "scorecard": scorecard,
        "defects": defects,
        "gap_entity_matrix": state.get("gap_entity_matrix") or
                             {"missing_entities": [], "missing_subtopics": [],
                              "competitor_advantages": []},
        "performance": perf,
        "root_causes": root_causes,
        "keep_list": keep_list,
    }
    validate_diagnosis(diagnosis)  # the seam contract, enforced at the source

    return {"diagnosis": diagnosis, "master_report_md": _report(diagnosis, state)}


def _report(d: dict, state: dict) -> str:
    lines = [
        f"# Master Audit Report — {d['url']}", "",
        f"- page type: **{d['page_type']}** · primary query: **{d['primary_query']}**",
        f"- defects: **{len(d['defects'])}** "
        f"({sum(1 for x in d['defects'] if x['severity'] == 'blocker')} blockers) · "
        f"keep-list items: **{len(d['keep_list'])}**", "",
        "## Scorecard", "", "| area | score (0-2) |", "|---|---|",
    ]
    lines += [f"| {a} | {s} |" for a, s in d["scorecard"].items()]
    for area, key in (("SERP", "serp_findings"), ("Authority", "authority_findings")):
        block = state.get(key) or {}
        if block.get("score_0_2") is None:
            note = block.get("note") or f"confidence: {block.get('confidence', 'n/a')}"
            lines.append(f"| {area.lower()} | not scored — {note} |")
    lines += ["", "## Defects (each owned by a content node)", ""]
    for sev in ("blocker", "major", "minor"):
        group = [x for x in d["defects"] if x["severity"] == sev]
        if group:
            lines.append(f"### {sev}")
            lines += [f"- {x['description']} → **{x['owning_step']}** — {x['fix']}" for x in group]
            lines.append("")
    lines += ["## Root causes", ""] + [f"- {r}" for r in d["root_causes"]]
    lines += ["", "## Keep list (a rebuild must NOT drop these)", ""]
    lines += [f"- {k}" for k in d["keep_list"]] or ["- (none identified)"]
    if d.get("performance", {}).get("aio_flag"):
        lines += ["", "## Performance note", "", f"> {d['performance']['aio_flag']}"]
    return "\n".join(lines) + "\n"
