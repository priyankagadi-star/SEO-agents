"""fetch_rendered(url) — httpx GET + HTML parse (BUILD-SPEC §7).

parse_html() is split out so audit nodes and tests can analyze local/fixture
HTML without network. No JS rendering in Phase 1+; the result carries that
limitation explicitly so downstream nodes report it instead of guessing at
client-rendered content.
"""
from __future__ import annotations

import json
import re

import httpx
from bs4 import BeautifulSoup

TIMEOUT_S = 20.0
RETRIES = 2


def parse_html(html: str, url: str, status_code: int = 200) -> dict:
    soup = BeautifulSoup(html, "html.parser")

    meta_desc = soup.find("meta", attrs={"name": "description"})
    robots_meta = soup.find("meta", attrs={"name": "robots"})
    viewport = soup.find("meta", attrs={"name": "viewport"})
    canonical_tag = soup.find("link", rel="canonical")

    jsonld = []
    for block in soup.find_all("script", type="application/ld+json"):
        try:
            jsonld.append(json.loads(block.string or ""))
        except (json.JSONDecodeError, TypeError):
            jsonld.append({"_parse_error": True, "_raw": (block.string or "")[:200]})

    text = soup.get_text(separator=" ", strip=True)
    return {
        "url": url,
        "status_code": status_code,
        "html": html,
        "text": text,
        "word_count": len(text.split()),
        "title": soup.title.get_text(strip=True) if soup.title else None,
        "meta_description": meta_desc.get("content") if meta_desc else None,
        "robots_meta": robots_meta.get("content") if robots_meta else None,
        "viewport": viewport.get("content") if viewport else None,
        "headings": [
            (int(h.name[1]), h.get_text(strip=True))
            for h in soup.find_all(["h1", "h2", "h3", "h4", "h5", "h6"])
        ],
        "images": [
            {"src": img.get("src", ""), "alt": img.get("alt"), "loading": img.get("loading")}
            for img in soup.find_all("img")
        ],
        "links": [a.get("href") for a in soup.find_all("a", href=True)],
        "jsonld": jsonld,
        "canonical": canonical_tag.get("href") if canonical_tag else None,
        "limitations": ["no-js-rendering: client-rendered content not captured (Phase 1 limitation)"],
    }


def fetch_rendered(url: str) -> dict:
    transport = httpx.HTTPTransport(retries=RETRIES)
    with httpx.Client(timeout=TIMEOUT_S, transport=transport, follow_redirects=True,
                      headers={"User-Agent": "seo-geo-platform/0.1 (+audit bot)"}) as client:
        resp = client.get(url)
    return parse_html(resp.text, url, status_code=resp.status_code)
