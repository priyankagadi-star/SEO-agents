"""c14_eeat (L4): author/testimonial/Person/Org ONLY from brand_assets.

Deterministic — this node is a constraint, not a writer. Missing material
becomes a human checkpoint, never an invented credential (BUILD-SPEC §5b).
"""
from __future__ import annotations


def run(state: dict) -> dict:
    brand = state.get("brand_assets") or {}
    hc = list(state.get("human_checkpoints", []))

    author = brand.get("author") or {}
    author_block = None
    if author.get("name"):
        author_block = {"name": author["name"],
                        "credentials": author.get("credentials", "")}
        if not author.get("credentials"):
            hc.append(f"[HUMAN] author '{author['name']}' has no credentials — supply them or the byline ships bare.")
    else:
        hc.append("[HUMAN] no author available — page will ship without a byline unless one is supplied.")

    approved = [t for t in brand.get("testimonials", [])
                if isinstance(t, dict) and t.get("permission") is True]
    excluded = [t for t in brand.get("testimonials", [])
                if not (isinstance(t, dict) and t.get("permission") is True)]
    if excluded:
        hc.append(f"[HUMAN] {len(excluded)} testimonial(s) excluded (permission!=true) — obtain written permission to use them.")

    return {
        "_eeat": {"author_block": author_block, "testimonials_used": approved},
        "human_checkpoints": hc,
        "_guardrails": [{"check": "eeat_from_brand_assets_only",
                         "author": bool(author_block),
                         "testimonials_used": len(approved),
                         "testimonials_excluded": len(excluded)}],
    }
