"""Real SEO research via the Semrush Analytics API (api.semrush.com).

The platform is a standalone CLI, so research is sourced from Semrush's HTTP API
(key in env SEMRUSH_API_KEY) — NOT the Semrush MCP server, which only exists
inside an interactive agent session. Responses are semicolon-delimited CSV.

Honest degradation: no key ⇒ {"stub": True} and callers keep volumes "unknown"
and SERP confidence "stub" exactly as before. The provider never fabricates.

Reports used:
  phrase_related   — related keywords (Ph, Nq volume, Kd difficulty, Cp)
  phrase_questions — question keywords (PAA-style intent)
  phrase_organic   — domains/URLs ranking for the phrase (real competitors)
"""
from __future__ import annotations

import os

BASE_URL = "https://api.semrush.com/"
_TIMEOUT = 30.0


def _parse_csv(text: str) -> list[dict]:
    """Semrush returns `;`-delimited CSV with a header row (or an ERROR line)."""
    text = (text or "").strip()
    if not text or text.upper().startswith("ERROR"):
        return []
    lines = text.splitlines()
    headers = [h.strip() for h in lines[0].split(";")]
    rows = []
    for line in lines[1:]:
        cells = line.split(";")
        if len(cells) == len(headers):
            rows.append(dict(zip(headers, cells)))
    return rows


def _num(s, cast=float):
    try:
        return cast(str(s).replace(",", "").strip())
    except (ValueError, AttributeError):
        return 0


class SemrushProvider:
    """Thin client over the Semrush Analytics API. `transport` is injectable
    for tests (httpx.MockTransport)."""

    def __init__(self, api_key: str | None = None, database: str = "us",
                 transport=None, timeout: float = _TIMEOUT):
        self.api_key = api_key or os.environ.get("SEMRUSH_API_KEY", "")
        self.database = database
        self._transport = transport
        self.timeout = timeout

    @property
    def available(self) -> bool:
        return bool(self.api_key)

    def _report(self, report_type: str, phrase: str, columns: str, limit: int) -> list[dict]:
        import httpx
        params = {"type": report_type, "key": self.api_key, "phrase": phrase,
                  "database": self.database, "export_columns": columns,
                  "display_limit": str(limit)}
        transport = self._transport or httpx.HTTPTransport(retries=2)
        with httpx.Client(timeout=self.timeout, transport=transport) as client:
            resp = client.get(BASE_URL, params=params)
        resp.raise_for_status()
        return _parse_csv(resp.text)

    def related_keywords(self, seed: str, limit: int = 30) -> list[dict]:
        rows = self._report("phrase_related", seed, "Ph,Nq,Kd,Cp,Co", limit)
        return [{"term": r.get("Keyword") or r.get("Ph", ""),
                 "volume": int(_num(r.get("Search Volume") or r.get("Nq"), float)),
                 "kd": _num(r.get("Keyword Difficulty Index") or r.get("Kd")),
                 "cpc": _num(r.get("CPC") or r.get("Cp"))} for r in rows if r]

    def questions(self, seed: str, limit: int = 20) -> list[str]:
        rows = self._report("phrase_questions", seed, "Ph,Nq", limit)
        return [r.get("Keyword") or r.get("Ph", "") for r in rows if (r.get("Keyword") or r.get("Ph"))]

    def organic_competitors(self, phrase: str, limit: int = 10) -> list[dict]:
        rows = self._report("phrase_organic", phrase, "Dn,Ur", limit)
        return [{"domain": r.get("Domain") or r.get("Dn", ""),
                 "url": r.get("Url") or r.get("Ur", "")} for r in rows if r]

    def research(self, seed: str) -> dict:
        """One call set feeding c3/c4/c5; honest stub when no key."""
        if not self.available:
            return {"stub": True, "keywords": [], "questions": [], "organic": [],
                    "note": "SEMRUSH_API_KEY not set — research stubbed"}
        return {"stub": False, "source": "semrush", "database": self.database,
                "keywords": self.related_keywords(seed),
                "questions": self.questions(seed),
                "organic": self.organic_competitors(seed)}


_PROVIDER: SemrushProvider | None = None


def get_provider() -> SemrushProvider:
    global _PROVIDER
    if _PROVIDER is None:
        _PROVIDER = SemrushProvider()
    return _PROVIDER


def set_provider(p) -> None:  # for tests
    global _PROVIDER
    _PROVIDER = p
