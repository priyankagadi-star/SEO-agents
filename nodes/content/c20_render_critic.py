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
_SEO = _CFG.get("seo_limits") or {}


def _len_findings(label: str, value: str, lo_hi: list[int] | None,
                  owning_step: str, severity: str = "minor") -> list[dict]:
    """Yield 0/1 finding when value chars fall outside [lo, hi]. lo=0 disables min check."""
    if not lo_hi or not value:
        return []
    lo, hi = lo_hi
    n = len(value)
    if lo and n < lo:
        return [{"description": f"{label} {n} chars < {lo}",
                 "owning_step": owning_step, "severity": severity,
                 "evidence": value[:120], "fix": f"Lengthen {label} to {lo}-{hi} chars."}]
    if hi and n > hi:
        return [{"description": f"{label} {n} chars > {hi}",
                 "owning_step": owning_step, "severity": severity,
                 "evidence": value[:120], "fix": f"Shorten {label} to {lo}-{hi} chars."}]
    return []


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
    # cta may come back as a string, dict ({text/label/cta/value}), or list —
    # real models vary the shape; coerce to a string before length checks.
    cta_raw = brief.get("cta") or ""
    if isinstance(cta_raw, dict):
        cta = str(cta_raw.get("text") or cta_raw.get("label") or cta_raw.get("cta")
                  or cta_raw.get("value") or next((v for v in cta_raw.values()
                                                   if isinstance(v, str)), ""))
    elif isinstance(cta_raw, (list, tuple)):
        cta = " ".join(str(x) for x in cta_raw)
    else:
        cta = str(cta_raw)
    if cta and len(cta.split()) > _LIMITS["cta_words"]:
        failures.append({"description": f"CTA '{cta}' > {_LIMITS['cta_words']} words",
                         "owning_step": "c8_brief_compiler", "severity": "major",
                         "evidence": cta, "fix": "Shorten the CTA."})

    # SEO length contracts (advisory). Title min, meta min, H1 min, AIO answer
    # block size, per-section H2 length, FAQ Q/A lengths, paragraph ceiling,
    # URL slug, image alt. Findings are minor — they surface but don't block.
    failures += _len_findings("title direction", title, _SEO.get("title_chars"), "c8_brief_compiler")
    failures += _len_findings("meta direction", meta, _SEO.get("meta_chars"), "c8_brief_compiler")
    h1 = (brief.get("title_direction") or "").strip()
    failures += _len_findings("H1", h1, _SEO.get("h1_chars"), "c8_brief_compiler")
    # AIO-citable answer block: prefer answer_first / what_it_does section body
    _sections = state.get("sections") or {}
    aio = _sections.get("answer_first") or _sections.get("what_it_does") or ""
    if aio:
        # strip fact refs + the first markdown heading line if present
        aio_clean = re.sub(r"\s*\(fact:[a-z0-9\-]+\)", "", aio, flags=re.I)
        aio_clean = re.sub(r"^#{1,3}\s.*\n", "", aio_clean).strip()
        failures += _len_findings("AIO answer block", aio_clean,
                                  _SEO.get("aio_answer_chars"), "c11_section_drafter")
    # H2 per outline section
    for s in (state.get("outline") or {}).get("sections", []):
        h2 = (s.get("h2") or "").strip()
        if h2:
            failures += _len_findings(f"H2 '{(s.get('id') or '')[:24]}'",
                                      h2, _SEO.get("h2_chars"), "c9_outline")
    # FAQ Q/A
    for i, item in enumerate(state.get("faq") or []):
        q = (item.get("q") if isinstance(item, dict) else "") or ""
        a = (item.get("a") if isinstance(item, dict) else "") or ""
        failures += _len_findings(f"FAQ Q[{i + 1}]", q, _SEO.get("faq_question_chars"), "c12_faq")
        failures += _len_findings(f"FAQ A[{i + 1}]", a, _SEO.get("faq_answer_chars"), "c12_faq")
    # Paragraph ceiling — only flag the worst overrun (avoid noise)
    para_max = (_SEO.get("paragraph_chars") or [0, 0])[1]
    if para_max:
        worst = max(((len(p), p[:80]) for p in re.split(r"\n\s*\n", draft) if p.strip()),
                    default=(0, ""))
        if worst[0] > para_max:
            failures.append({"description": f"longest paragraph {worst[0]} chars > {para_max}",
                             "owning_step": "c11_section_drafter", "severity": "minor",
                             "evidence": worst[1], "fix": "Split into 2-3 paragraphs."})
    # URL slug
    target = (state.get("target_url") or (state.get("research_dossier") or {}).get("target_url") or "").strip()
    if target:
        slug = target.rstrip("/").split("/")[-1]
        failures += _len_findings("URL slug", slug, _SEO.get("url_slug_chars"), "c0_seed")
        if slug and not re.fullmatch(r"[a-z0-9][a-z0-9-]*", slug):
            failures.append({"description": f"URL slug '{slug}' not lowercase-with-hyphens",
                             "owning_step": "c0_seed", "severity": "minor",
                             "evidence": slug, "fix": "Use lowercase letters, digits, and hyphens only."})
    # Raw HTML in section bodies. The writer should use markdown — raw HTML
    # bypasses the editor's escaping, leaks UI mock code, and the renderer has
    # to special-case it. Flag any <table>/<form>/<script>/<style>/<iframe>.
    _RAW = re.compile(r"<\s*(table|form|script|style|iframe|object|embed)\b", re.I)
    for sid, body in _sections.items():
        m = _RAW.search(body or "")
        if m:
            failures.append({
                "description": f"raw HTML <{m.group(1).lower()}> in section '{sid}'",
                "owning_step": "c11_section_drafter", "severity": "minor",
                "evidence": (body or "")[max(0, m.start() - 30): m.start() + 80],
                "fix": "Replace raw HTML with markdown (use | tables, lists). Only "
                       "tool_widget / UI placeholder slots are exempt — and the writer "
                       "should leave those empty."})

    # Image alt text (when present in manifest)
    for item in manifest:
        alt = (item.get("alt") or item.get("alt_text") or "").strip()
        if alt:
            failures += _len_findings(f"image alt '{(item.get('filename') or '')[:24]}'",
                                      alt, _SEO.get("image_alt_chars"), "c15_media")

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
