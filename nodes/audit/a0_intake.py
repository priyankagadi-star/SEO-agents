"""a0_intake: fetch+parse the URL, parse GSC export if provided, classify
page_type + primary_query. Deterministic heuristics; honest fallbacks."""
from __future__ import annotations

import re

from tools.fetch import fetch_rendered
from tools.gsc import parse_gsc_export

_TYPE_RULES = [
    ("comparison", re.compile(r"\bvs\.?\b|\bversus\b|\bcompared?\b|\balternatives?\b", re.I)),
    ("blog-listicle", re.compile(r"\btop\s+\d+|\b\d+\s+(best|ways|tools|tips)\b|\bbest\s+\d+", re.I)),
    ("glossary", re.compile(r"^what\s+is\b|\bdefinition\b|\bglossary\b|\bmeaning\b", re.I)),
    ("guide", re.compile(r"\bguide\b|\bhow\s+to\b|\btutorial\b|\bstep[-\s]by[-\s]step\b", re.I)),
    ("landing", re.compile(r"\bpricing\b|\bsign\s*up\b|\bdemo\b|\bget\s+started\b", re.I)),
]


def classify_page_type(title: str, url: str, text_head: str) -> str:
    basis = f"{title} {url.rsplit('/', 1)[-1].replace('-', ' ')}"
    for ptype, pat in _TYPE_RULES:
        if pat.search(basis):
            return ptype
    # landing cues live in the page body more than the title
    if _TYPE_RULES[4][1].search(text_head):
        return "feature"
    return "feature"


def derive_primary_query(page: dict, keyword_hint: str | None) -> str:
    if keyword_hint:
        return keyword_hint
    h1s = [t for lvl, t in page.get("headings", []) if lvl == 1]
    basis = h1s[0] if h1s else (page.get("title") or page["url"])
    basis = re.split(r"\s+[|\-–—]\s+", basis)[0]  # strip brand suffix
    return basis.strip().lower()


def run(state: dict) -> dict:
    page = fetch_rendered(state["url"])
    gsc = {}
    if state.get("gsc_path"):
        gsc = parse_gsc_export(state["gsc_path"])
    page_type = classify_page_type(page.get("title") or "", state["url"], page["text"][:600])
    return {
        "page": page,
        "page_type": page_type,
        "primary_query": derive_primary_query(page, state.get("primary_query")),
        "gsc": gsc,
    }
