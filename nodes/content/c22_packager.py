"""c22_packager (L7): assemble the deliverable. Adds nothing; arranges.

Unresolved [VERIFY]/[HUMAN] items are listed explicitly in human_checkpoints —
never dropped.
"""
from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path

import yaml

_CFG = yaml.safe_load((Path(__file__).parents[2] / "config.yaml").read_text())
_H1 = _CFG["ui_limits"]["h1_chars"]
_META = _CFG["ui_limits"]["meta_chars"]


def _title_variants(brief: dict, keyword: str) -> list[str]:
    base = brief.get("title_direction") or keyword
    candidates = [
        base,
        f"{keyword.title()}: A Practical Guide",
        f"How to Improve {keyword.title()}",
    ]
    out: list[str] = []
    for c in candidates:
        c = c[:_H1].strip()
        if c and c not in out:
            out.append(c)
    while len(out) < 3:
        out.append((base + f" ({len(out)+1})")[:_H1])
    return out[:3]


def _byline(state: dict, today: str) -> dict | None:
    """E-E-A-T: every published page must carry an author + last-updated.
    Pulls the author from brand_assets (the permission-gated factual source)
    and falls back to the [HUMAN] checkpoint c14 already emits when missing."""
    a = (state.get("brand_assets") or {}).get("author") or {}
    name = (a.get("name") or "").strip()
    if not name:
        return None
    parts = [name]
    if a.get("title"):
        parts.append(a["title"])
    if a.get("company"):
        parts.append(a["company"])
    return {
        "name": name,
        "title": a.get("title", ""),
        "company": a.get("company", ""),
        "display": " · ".join(parts),                       # "Chalam PVS · Founder · Siftly"
        "credentials": a.get("credentials", ""),
        "linkedin": a.get("linkedin", ""),
        "byline_line": f"Written by {' · '.join(parts)} · Last updated {today}",
    }


def _iso_date_today() -> str:
    """E-E-A-T freshness signal. Format matches "16 June 2026" style."""
    return datetime.now(timezone.utc).strftime("%-d %B %Y")


def _attach_byline_to_schema(schema: dict, byline: dict | None, last_updated_iso: str) -> dict:
    """Inject author + dateModified into the JSON-LD @graph — Google reads
    these directly for E-E-A-T + freshness."""
    if not isinstance(schema, dict):
        return schema
    graph = schema.get("@graph") or ([schema] if schema.get("@type") else [])
    if not graph:
        return schema
    page = next((b for b in graph if isinstance(b, dict) and b.get("@type") in ("WebPage", "Article")), graph[0])
    if isinstance(page, dict):
        page["dateModified"] = last_updated_iso
        if byline:
            person = {"@type": "Person", "name": byline["name"]}
            if byline.get("title") or byline.get("company"):
                person["jobTitle"] = ", ".join(x for x in (byline.get("title"), byline.get("company")) if x)
            if byline.get("linkedin"):
                person["sameAs"] = [byline["linkedin"]]
            page["author"] = person
    schema["@graph"] = graph
    return schema


def run(state: dict) -> dict:
    brief = state.get("brief") or {}
    draft = state.get("draft", "")
    runlog = state.get("_runlog", [])

    today_display = _iso_date_today()                                   # "24 June 2026"
    today_iso = datetime.now(timezone.utc).strftime("%Y-%m-%d")         # "2026-06-24" (for schema)
    byline = _byline(state, today_display)

    unresolved = list(state.get("verify_list") or [])
    human_checkpoints = list(state.get("human_checkpoints") or [])
    if byline is None:
        msg = "[HUMAN] no author in brand_assets — Google E-E-A-T requires a real byline. Add {name, title, company} before publishing."
        if msg not in human_checkpoints:
            human_checkpoints.append(msg)

    schema = _attach_byline_to_schema(state.get("schema_jsonld", {}) or {}, byline, today_iso)

    package_out = {
        "title_variants": _title_variants(brief, state["primary_keyword"]),
        "meta": (brief.get("meta_direction") or f"{state['primary_keyword']} — learn how it works.")[:_META],
        "byline": byline,
        "byline_line": byline["byline_line"] if byline else None,
        "last_updated": today_display,
        "last_updated_iso": today_iso,
        "full_copy": draft,
        "schema_jsonld": schema,
        "media_manifest": state.get("media_plan") or [],
        "internal_links": brief.get("internal_link_targets", []),
        "qa_checklist": [{"node": e["node"], "guardrails": e.get("guardrails", [])} for e in runlog],
        "human_checkpoints": human_checkpoints,
        "unresolved_verify": unresolved,
        "measurement_plan": {
            "primary_metric": (state.get("success_metric") or {}).get("metric", "AI-citation share"),
            "review_after": "4 weeks",
            "note": "Judge on AI-citation share where GSC CTR is structurally suppressed.",
        },
    }
    return {"package_out": package_out,
            "_guardrails": [{"check": "packaged", "byline": bool(byline), "last_updated": today_display}]}
