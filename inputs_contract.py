"""Input contract for content runs (architecture: run.py precondition).

The owner's hard rule: you cannot generate a page from nothing.

- EXISTING page (optimize/rebuild): must supply the page URL AND its GSC data,
  so the writer mirrors how people actually search for that page and the critic
  can enforce intent-fit. No GSC -> we'd be optimizing blind.
- NEW page (net_new): must supply a seed keyword AND real research data —
  Semrush (API key or MCP) or an export carrying market_stats / external_sources
  / real_questions — so volumes, questions and citations are real, never invented.

Deterministic; no model calls. Returns (state, errors); run.py blocks on errors.
"""
from __future__ import annotations


def classify_page_state(mode: str, target_url: str | None,
                        gsc_available: bool, research_dossier: dict | None) -> str:
    """existing (optimize a live URL) vs new (create from a seed)."""
    explicit = (research_dossier or {}).get("page_status")
    if explicit in ("existing", "new"):
        return explicit
    if mode == "rebuild":
        return "existing"
    if target_url and gsc_available:
        return "existing"
    return "new"


def validate_content_inputs(*, mode: str, seed_keyword: str | None,
                            target_url: str | None, gsc_available: bool,
                            semrush_available: bool,
                            research_dossier: dict | None) -> tuple[str, list[str]]:
    rd = research_dossier or {}
    state = classify_page_state(mode, target_url, gsc_available, rd)
    errors: list[str] = []
    if state == "existing":
        if not target_url:
            errors.append("existing page: missing page URL "
                          "(set research_dossier.target_url, or use --mode rebuild --diagnosis)")
        if not gsc_available:
            errors.append("existing page: missing GSC data — pass --gsc <export.zip> "
                          "or drop the page's GSC export in the brand's gsc/ folder")
    else:
        if not (seed_keyword or rd.get("seed_keyword")):
            errors.append("new page: missing seed keyword")
        has_research = bool(rd.get("market_stats") or rd.get("external_sources")
                            or rd.get("real_questions")) or semrush_available
        if not has_research:
            errors.append("new page: missing research data — enable Semrush "
                          "(SEMRUSH_API_KEY or the Semrush MCP) or provide an export with "
                          "market_stats / external_sources / real_questions")
    return state, errors
