"""serp_search(query) — SERP interface (BUILD-SPEC §7).

Phase 1: fixture-backed stub. Every stub response carries {"stub": True} and
consuming nodes MUST propagate confidence:"stub" — never fabricate SERP data.
Phase 3: real provider behind the same interface (env SERP_API_KEY, provider
per config).
"""
from __future__ import annotations

import json
import os
import re
from pathlib import Path

_FIXTURES = Path(__file__).parent.parent / "eval" / "fixtures" / "serp"


def _slug(query: str) -> str:
    return re.sub(r"[^a-z0-9]+", "-", query.lower()).strip("-")


def serp_search(query: str) -> dict:
    if os.environ.get("SERP_API_KEY"):
        return _real_search(query)
    fixture = _FIXTURES / f"{_slug(query)}.json"
    if fixture.exists():
        data = json.loads(fixture.read_text())
        return {"stub": True, "organic": data.get("organic", []), "paa": data.get("paa", [])}
    return {
        "stub": True,
        "organic": [],
        "paa": [],
        "note": f"no fixture for '{query}' (expected {fixture.name}); SERP data unavailable",
    }


def _real_search(query: str) -> dict:
    raise NotImplementedError(
        "Real SERP provider is a Phase 3 deliverable (BUILD-SPEC §7); "
        "wire the provider named in config.yaml behind this interface."
    )
