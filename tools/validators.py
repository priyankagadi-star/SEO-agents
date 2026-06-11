"""Deterministic HTML validators (BUILD-SPEC §7). No model calls."""
from __future__ import annotations

import json
import re
from urllib.parse import urljoin, urlparse

from bs4 import BeautifulSoup

REQUIRED_KEYS = {
    "FAQPage": ["mainEntity"],
    "SoftwareApplication": ["name", "applicationCategory"],
    "Person": ["name"],
}


def validate_jsonld(html: str) -> dict:
    """Parse every ld+json block; report JSON validity + required keys per @type."""
    soup = BeautifulSoup(html, "html.parser")
    blocks, errors = [], []
    for i, script in enumerate(soup.find_all("script", type="application/ld+json")):
        raw = script.string or ""
        try:
            data = json.loads(raw)
        except json.JSONDecodeError as e:
            errors.append({"block": i, "error": f"invalid JSON: {e}"})
            continue
        items = data.get("@graph", [data]) if isinstance(data, dict) else data
        for item in items if isinstance(items, list) else [items]:
            if not isinstance(item, dict):
                continue
            blocks.append(item)
            t = item.get("@type")
            for key in REQUIRED_KEYS.get(t, []):
                if key not in item:
                    errors.append({"block": i, "type": t, "error": f"missing required key '{key}'"})
    return {"blocks": blocks, "errors": errors, "valid": not errors, "count": len(blocks)}


def check_links(html: str, base_url: str) -> dict:
    """Classify links; flag empty/fragment/javascript hrefs. (Liveness checks are a node concern.)"""
    soup = BeautifulSoup(html, "html.parser")
    base_host = urlparse(base_url).netloc
    internal, external, suspect = [], [], []
    for a in soup.find_all("a", href=True):
        href = a["href"].strip()
        if not href or href.startswith(("#", "javascript:", "mailto:")):
            suspect.append(href or "(empty)")
            continue
        absolute = urljoin(base_url, href)
        (internal if urlparse(absolute).netloc == base_host else external).append(absolute)
    return {"internal": internal, "external": external, "suspect": suspect,
            "internal_count": len(internal)}


def image_seo_audit(html: str) -> dict:
    """Alt coverage, base64 count, hero loading attr, filename descriptiveness."""
    soup = BeautifulSoup(html, "html.parser")
    imgs = soup.find_all("img")
    total = len(imgs)
    with_alt = sum(1 for i in imgs if (i.get("alt") or "").strip())
    base64_count = sum(1 for i in imgs if (i.get("src") or "").startswith("data:"))

    hero = imgs[0] if imgs else None
    hero_lazy = bool(hero is not None and hero.get("loading") == "lazy")

    def descriptive(src: str) -> bool:
        name = src.rsplit("/", 1)[-1].split("?")[0].rsplit(".", 1)[0]
        # heuristic: hyphenated words, not hashes/UUIDs/IMG_1234
        if re.fullmatch(r"(img|image|photo|screenshot)?[_\-]?\d+", name, re.I):
            return False
        if re.fullmatch(r"[0-9a-f\-]{16,}", name, re.I):
            return False
        return bool(re.search(r"[a-z]{3,}(-[a-z0-9]+)+", name, re.I)) or len(name) > 8

    descriptive_count = sum(
        1 for i in imgs
        if (src := i.get("src") or "") and not src.startswith("data:") and descriptive(src)
    )
    return {
        "total": total,
        "alt_coverage": (with_alt / total) if total else 1.0,
        "base64_count": base64_count,
        "hero_lazy_loaded": hero_lazy,
        "descriptive_filenames": descriptive_count,
        "violations": (
            (["hero image is lazy-loaded"] if hero_lazy else [])
            + ([f"{base64_count} base64 data-URI images"] if base64_count else [])
            + ([f"alt coverage {with_alt}/{total}"] if with_alt < total else [])
        ),
    }
