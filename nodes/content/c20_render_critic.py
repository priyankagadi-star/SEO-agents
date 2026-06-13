"""c20_render_critic (L6): pixel-level checks. Deterministic.

H1/meta/CTA length limits from config; named-entity integrity: when a verified
fact's value enumerates names (e.g. "4 (ChatGPT, Claude, Perplexity, Google AI
Overviews)") and the fact is cited in the draft, every enumerated name must
actually appear — a count without its members is how "4 engines" silently
becomes three names and a vibe.
"""
from __future__ import annotations

import re
from pathlib import Path

import yaml

from ledger import FactsLedger
from page_profiles import get_profile

_CFG = yaml.safe_load((Path(__file__).parents[2] / "config.yaml").read_text())
_LIMITS = _CFG["ui_limits"]


def run(state: dict) -> dict:
    brief = state.get("brief") or {}
    draft = state.get("draft", "")
    manifest = state.get("media_manifest") or []
    failures = []

    title = brief.get("title_direction") or ""
    if len(title) > _LIMITS["h1_chars"]:
        failures.append({"description": f"title direction {len(title)} chars > {_LIMITS['h1_chars']}",
                         "owning_step": "c8_brief_compiler", "severity": "major",
                         "evidence": title, "fix": "Shorten the title direction."})
    meta = brief.get("meta_direction") or ""
    if len(meta) > _LIMITS["meta_chars"]:
        failures.append({"description": f"meta direction {len(meta)} chars > {_LIMITS['meta_chars']}",
                         "owning_step": "c8_brief_compiler", "severity": "major",
                         "evidence": meta, "fix": "Shorten the meta direction."})
    cta = brief.get("cta") or ""
    if cta and len(cta.split()) > _LIMITS["cta_words"]:
        failures.append({"description": f"CTA '{cta}' > {_LIMITS['cta_words']} words",
                         "owning_step": "c8_brief_compiler", "severity": "major",
                         "evidence": cta, "fix": "Shorten the CTA."})

    # named-entity integrity vs ledger enumerations
    led = FactsLedger(list(state.get("facts_ledger", [])))
    for f in led.facts:
        if f["status"] != "verified" or f"(fact:{f['id']})" not in draft:
            continue
        m = re.search(r"\(([^()]+,[^()]+)\)", f["value"])
        if not m:
            continue
        names = [n.strip() for n in m.group(1).split(",") if n.strip()]
        missing = [n for n in names if n.lower() not in draft.lower()]
        if missing:
            failures.append({"description": f"fact '{f['id']}' cited but enumerated names missing from copy: {missing}",
                             "owning_step": "c11_section_drafter", "severity": "blocker",
                             "evidence": f["value"],
                             "fix": "Name every member the locked fact enumerates."})

    # manifest honored: every manifest image referenced or placed in a known section
    section_ids = {s.get("id") for s in (state.get("outline") or {}).get("sections", [])}
    for item in manifest:
        placed = item.get("placement") in section_ids or item.get("filename", "") in draft
        if not placed and item.get("type") != "screenshot":
            failures.append({"description": f"manifest image '{item.get('filename')}' not placed in any known section",
                             "owning_step": "c15_media", "severity": "major",
                             "evidence": str(item.get("placement")),
                             "fix": "Assign the image to an existing section id."})

    # page-type structure contract: required blocks must reach the draft
    profile = get_profile(state.get("page_type"))
    for block in profile.missing_blocks(draft, state.get("outline")):
        failures.append({"description": f"{profile.page_type} page missing required block: {block.label}",
                         "owning_step": "c9_outline", "severity": "major",
                         "evidence": f"no cue for '{block.id}' in draft/outline",
                         "fix": f"Add a section covering '{block.label}'."})

    # media gate (G6): a visual page type with zero images FAILS. SVG diagrams
    # count; screenshots requested as [HUMAN] count; base64 never allowed.
    _NEEDS_MEDIA = {"feature", "comparison", "guide", "listicle", "blog-listicle"}
    if profile.page_type in _NEEDS_MEDIA and not manifest:
        failures.append({"description": f"{profile.page_type} page has zero visual assets",
                         "owning_step": "c15_media", "severity": "blocker",
                         "evidence": "empty media_manifest",
                         "fix": "Add at least one hosted SVG diagram or a [HUMAN] screenshot request."})
    for item in manifest:
        if str(item.get("filename", "")).startswith("data:"):
            failures.append({"description": f"base64 image in manifest: {str(item.get('filename'))[:40]}",
                             "owning_step": "c15_media", "severity": "blocker",
                             "evidence": "data: URI", "fix": "Serve images as files, never base64."})

    blockers = [x for x in failures if x["severity"] == "blocker"]
    return {"render_report": {"verdict": "fail" if blockers else "pass",
                              "page_type": profile.page_type,
                              "failures": failures},
            "_guardrails": [{"check": "render_critic",
                             "verdict": "fail" if blockers else "pass",
                             "failures": len(failures)}]}
