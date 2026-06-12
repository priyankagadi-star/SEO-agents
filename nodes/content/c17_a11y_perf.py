"""c17_a11y_perf (L5): alt coverage 100%, heading order, no data: URIs,
hero fetchpriority. Deterministic checks over draft + manifest."""
from __future__ import annotations

import re


def run(state: dict) -> dict:
    draft = state.get("draft", "")
    manifest = state.get("media_manifest") or []
    violations = []

    for m in manifest:
        if not (m.get("alt") or "").strip():
            violations.append(f"image '{m.get('filename')}' missing alt text")
        if str(m.get("filename", "")).startswith("data:"):
            violations.append(f"data: URI image in manifest: {str(m.get('filename'))[:40]}")

    if manifest:
        hero = manifest[0]
        if hero.get("loading") != "eager" or hero.get("fetchpriority") != "high":
            violations.append("hero image must be loading=eager with fetchpriority=high")

    if "data:image" in draft:
        violations.append("data: URI embedded in draft copy")

    levels = [len(m.group(1)) for m in re.finditer(r"^(#{1,6})\s", draft, re.M)]
    skips = [(a, b) for a, b in zip(levels, levels[1:]) if b - a > 1]
    if skips:
        violations.append(f"heading level skips in draft: {skips}")

    return {"_guardrails": [{"check": "a11y_perf", "violations": violations,
                             "ok": not violations}],
            "_a11y_violations": violations}
