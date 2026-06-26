#!/usr/bin/env python3
"""Turn the Siftly keyword/site-structure sheet into per-page pipeline inputs.

Reads the master CSV, selects the requested feature pages, and writes one
inputs/<slug>.json per page with a research_dossier built from the sheet row
(H1, quotable intro, key sections, links, CTA, primary keyword) plus a shared
real-research base (Semrush market stats + authoritative external sources +
real PAA) so the GOAL gate has citations/data to credit. Deterministic.
"""
import csv
import json
import re
from pathlib import Path

CSV = Path("/root/.claude/uploads/5a0795d6-5e51-55c1-85bb-47f0134a6eb0/65d4dbfe-Siftly_Keyword_Target_Master__SiteStructure1.csv")
OUT = Path("brands/siftly.ai/inputs/batch")
OUT.mkdir(parents=True, exist_ok=True)

# requested page URL -> CSV row URL (alias where the sheet renamed it)
REQUESTED = {
    "/features/ai-brand-monitoring": "/features/ai-brand-monitoring",
    "/features/ai-citation-tracking": "/features/citation-intelligence",
    "/features/chatgpt-visibility": "/features/chatgpt-visibility",
    "/features/competitor-benchmarking": "/features/competitor-benchmarking",
    "/features/share-of-voice": "/features/share-of-voice",
    "/features/geo-content": "/features/geo-content",
    "/features/brand-brief": "/features/brand-brief",
    "/features/brand-voice": "/features/brand-voice",
    "/features/brand-visual-identity": "/features/brand-visual-identity",
    "/features/social-community": "/features/social-community",
    "/features/citation-outreach": "/features/citation-outreach",
}

# shared real research (Semrush US, fetched via MCP earlier; sheet vols are Semrush US too)
SHARED = {
    "market_stats": [
        {"stat": "~5,400 monthly US searches for 'generative engine optimization'", "source": "Semrush"},
        {"stat": "~2,400/mo for 'ai visibility tool'", "source": "Semrush"},
        {"stat": "~1,600/mo for 'answer engine optimization'", "source": "Semrush"},
        {"stat": "~590/mo for 'best ai visibility tools'", "source": "Semrush"},
    ],
    "external_sources": [
        {"name": "Search Engine Land — What is GEO", "url": "https://searchengineland.com/what-is-generative-engine-optimization-geo-444418"},
        {"name": "arXiv — Generative Engine Optimization (research)", "url": "https://arxiv.org/abs/2509.08919"},
        {"name": "Google Search Central — AI features & your site", "url": "https://developers.google.com/search/docs/fundamentals/ai-optimization-guide"},
        {"name": "Forbes — GEO: The Future of Search Is Here", "url": "https://www.forbes.com/councils/forbesagencycouncil/2025/01/02/generative-engine-optimization-geo-the-future-of-search-is-here/"},
    ],
    "real_questions": [
        "How to improve brand visibility in AI search engines",
        "How to monitor AI search visibility",
        "What are the best AI search visibility tools",
        "How to check the AI visibility of my brand",
        "Why should I track AI brand visibility",
        "How to improve visibility in Google AI Overviews",
    ],
    "trend_signals": [
        "According to Semrush (US, 2026), demand for 'generative engine optimization' has grown roughly 3x over the past year.",
        "Google Search Central now publishes guidance on being eligible for AI Overviews (developers.google.com).",
        "Search Engine Land and Forbes both now cover generative engine optimization as a distinct discipline.",
    ],
}


def slug(url):
    return url.strip("/").replace("/", "-")


def split_sections(s):
    return [x.strip() for x in re.split(r"[·•|]", s or "") if x.strip()]


def split_links(s):
    return [x.strip() for x in re.split(r"[,;]", s or "") if x.strip() and x.strip() != "—"]


# index CSV rows by URL
rows = {}
with CSV.open() as f:
    reader = csv.reader(f)
    data = list(reader)
header_i = next(i for i, r in enumerate(data) if r and r[0] == "URL")
hdr = data[header_i]
for r in data[header_i + 1:]:
    if r and r[0].startswith("/"):
        rows[r[0]] = dict(zip(hdr, r))

manifest = []
for req_url, csv_url in REQUESTED.items():
    row = rows.get(csv_url)
    if not row:
        print("!! no sheet row for", csv_url)
        continue
    rd = {
        "purpose": row.get("Purpose", ""),
        "suggested_h1": row.get("H1 (suggested)", ""),
        "quotable_intro": row.get("Quotable intro (40-60 words, AI-citable)", ""),
        "key_sections": split_sections(row.get("Key sections (structure)", "")),
        "links_up": split_links(row.get("Links up →", "")),
        "links_cross": split_links(row.get("Links down / cross", "")),
        "primary_cta": row.get("Primary CTA", "Book a demo"),
        "secondary_keyword": row.get("Secondary kw", ""),
        "schema_types": split_sections(row.get("Schema", "")),
        "target_url": req_url,
        **SHARED,
    }
    # real sourced demand for THIS page's own keyword (sheet vol = Semrush US)
    vol = (row.get("Vol") or "").strip()
    if vol and vol not in ("<10", "n/a", "TBD", "0"):
        rd["market_stats"] = [{"stat": f"~{vol}/mo US searches for '{row['Primary keyword']}'",
                               "source": "Semrush"}] + rd["market_stats"]
    inp = {
        "seed_keyword": row.get("Primary keyword", "").strip(),
        "page_type": "feature",
        "business_context": (f"Siftly feature page. {row.get('Purpose','')} "
                             f"Intent: {row.get('Intent','')}. Keyword difficulty: {row.get('KD','')}."),
        "research_dossier": rd,
    }
    path = OUT / f"{slug(req_url)}.json"
    path.write_text(json.dumps(inp, indent=2, ensure_ascii=False))
    manifest.append({"url": req_url, "csv_url": csv_url, "status": row.get("Status"),
                     "seed": inp["seed_keyword"], "inputs": str(path)})

(OUT / "_manifest.json").write_text(json.dumps(manifest, indent=2, ensure_ascii=False))
print(f"wrote {len(manifest)} input files to {OUT}")
for m in manifest:
    print(f"  {m['url']:42s} [{m['status']:8s}] seed={m['seed']!r}")
