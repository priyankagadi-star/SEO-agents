"""Prompt loader (BUILD-SPEC §8).

- One .md per node under prompts/audit/ or prompts/content/ (inferred from id).
- str.format substitution; a missing variable is a hard error (KeyError).
- EVERY content prompt gets the non-negotiable RULES block appended
  programmatically — the .md files are never trusted to carry it.
"""
from __future__ import annotations

from pathlib import Path

_PROMPTS_DIR = Path(__file__).parent

RULES_BLOCK = """
RULES (non-negotiable):
- Assert only facts present in the FACTS LEDGER below or directly quoted from CANONICAL SOURCES.
- A missing fact must be written as [VERIFY: what is missing]. Never invent a number, source, feature, credential, quote, or URL.
- When citing a ledger fact inline, append its id like (fact:engines-count).
- Output ONLY the JSON object matching the schema given. No prose around it.
FACTS LEDGER:
{ledger_markdown}
"""


def _pipeline_for(node_id: str) -> str:
    if node_id.startswith("a"):
        return "audit"
    if node_id.startswith("c"):
        return "content"
    raise ValueError(f"Cannot infer pipeline from node id '{node_id}'")


def load_prompt(node_id: str, **vars) -> str:
    """Load + render the prompt for a node. Missing template var = hard error."""
    pipeline = _pipeline_for(node_id)
    path = _PROMPTS_DIR / pipeline / f"{node_id}.md"
    if not path.exists():
        raise FileNotFoundError(f"No prompt file for node '{node_id}' at {path}")
    template = path.read_text()
    if pipeline == "content":
        template = template.rstrip() + "\n" + RULES_BLOCK
        vars.setdefault("ledger_markdown", "(ledger is empty)")
    try:
        return template.format(**vars)
    except KeyError as e:
        raise KeyError(f"Prompt '{node_id}' requires missing variable: {e}") from e
