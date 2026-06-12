"""c15_media (L4): media manifest + simple SVG diagrams. Deterministic.

Zero base64 by construction; screenshots become [HUMAN] checkpoints, never
faked; hero is eager with fetchpriority=high; alt text describes the actual
asset (the diagram we generated), not keywords.
"""
from __future__ import annotations

import re


def _kebab(s: str) -> str:
    return re.sub(r"[^a-z0-9]+", "-", s.lower()).strip("-")[:60]


def _diagram_svg(title: str, steps: list[str]) -> str:
    """A clean labeled-boxes flow diagram — self-contained SVG, no external refs."""
    w, box_h, gap, pad = 720, 56, 24, 16
    h = pad * 2 + 40 + len(steps) * (box_h + gap)
    parts = [
        f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {w} {h}" role="img" aria-label="{title}">',
        f'<title>{title}</title>',
        f'<text x="{w // 2}" y="{pad + 12}" text-anchor="middle" font-family="system-ui" font-size="18" font-weight="600">{title}</text>',
    ]
    y = pad + 40
    for i, step in enumerate(steps):
        parts.append(f'<rect x="60" y="{y}" width="{w - 120}" height="{box_h}" rx="8" fill="#eef2ff" stroke="#4f46e5"/>')
        parts.append(f'<text x="{w // 2}" y="{y + box_h // 2 + 5}" text-anchor="middle" font-family="system-ui" font-size="14">{step}</text>')
        if i < len(steps) - 1:
            ay = y + box_h
            parts.append(f'<line x1="{w // 2}" y1="{ay}" x2="{w // 2}" y2="{ay + gap}" stroke="#4f46e5" marker-end="none"/>')
            parts.append(f'<polygon points="{w // 2 - 5},{ay + gap - 6} {w // 2 + 5},{ay + gap - 6} {w // 2},{ay + gap}" fill="#4f46e5"/>')
        y += box_h + gap
    parts.append("</svg>")
    return "".join(parts)


def run(state: dict) -> dict:
    outline = state.get("outline") or {}
    sections = outline.get("sections", [])
    brief_media = (state.get("brief") or {}).get("media_plan") or []
    hc = list(state.get("human_checkpoints", []))

    manifest, svg_assets = [], {}

    # one overview diagram from the outline structure (drawable -> we draw it)
    if sections:
        steps = [s.get("h2", s.get("id", "")) for s in sections][:6]
        title = f"How {state['primary_keyword']} works"
        fname = f"{_kebab(state['primary_keyword'])}-overview.svg"
        svg_assets[fname] = _diagram_svg(title, steps)
        manifest.append({
            "filename": fname,
            "alt": f"Flow diagram: {title} in {len(steps)} steps: {', '.join(steps)}",
            "width": 720, "height": 80 + len(steps) * 80,
            "loading": "eager", "fetchpriority": "high",   # hero
            "placement": sections[0].get("id", "s1"),
            "type": "svg",
        })

    # planned items we cannot draw (screenshots) -> human checkpoints, never faked
    for item in brief_media:
        kind = str(item.get("type", item)).lower()
        if "screenshot" in kind or "photo" in kind:
            hc.append(f"[HUMAN] supply real screenshot for media plan item: {item}")
        # diagrams beyond the overview would be added here the same way

    screenshots = state.get("brand_assets", {}).get("screenshots") or []
    for shot in screenshots:
        if isinstance(shot, dict) and shot.get("file"):
            manifest.append({
                "filename": shot["file"],
                "alt": shot.get("alt", ""),
                "width": shot.get("width"), "height": shot.get("height"),
                "loading": "lazy",
                "placement": shot.get("placement", "body"),
                "type": "screenshot",
            })
            if not shot.get("alt"):
                hc.append(f"[HUMAN] write alt text describing what screenshot '{shot['file']}' actually shows.")

    base64_count = sum(1 for m in manifest if str(m.get("filename", "")).startswith("data:"))
    return {
        "media_manifest": manifest,
        "svg_assets": svg_assets,
        "human_checkpoints": hc,
        "_guardrails": [{"check": "media", "items": len(manifest),
                         "base64": base64_count, "ok": base64_count == 0}],
    }
