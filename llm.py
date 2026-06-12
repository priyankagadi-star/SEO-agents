"""Model-call layer (BUILD-SPEC §2, §8).

- Two tiers from config.yaml: strong / fast.
- call_node(node_id, tier, **vars): load prompt → call model → parse JSON
  (strip fences; retry once with the error appended; then raise).
- The client is injectable: tests and the `--fake` CLI flag set a ScriptedLLM
  via set_client(); a real run uses the Anthropic SDK (needs ANTHROPIC_API_KEY).
"""
from __future__ import annotations

import json
import re
from pathlib import Path

import yaml

from prompts import load_prompt

_CONFIG = yaml.safe_load((Path(__file__).parent / "config.yaml").read_text())
_MODELS = _CONFIG["models"]
_PRICING = _CONFIG.get("pricing", {})

_CLIENT = None

# pending usage events; the graph node wrapper drains these into the runlog
_USAGE_LOG: list[dict] = []


def _cost_usd(tier: str, input_tokens: int, output_tokens: int) -> float:
    p = _PRICING.get(tier, {})
    return round(
        input_tokens * p.get("input_per_mtok", 0) / 1e6
        + output_tokens * p.get("output_per_mtok", 0) / 1e6,
        6,
    )


def record_usage(node_id: str, tier: str, usage: dict) -> None:
    _USAGE_LOG.append({
        "node": node_id,
        "model": usage.get("model"),
        "input_tokens": usage.get("input_tokens", 0),
        "output_tokens": usage.get("output_tokens", 0),
        "cost_usd": _cost_usd(tier, usage.get("input_tokens", 0), usage.get("output_tokens", 0)),
    })


def drain_usage() -> list[dict]:
    """Return + clear pending usage events (called by the node wrapper)."""
    out = list(_USAGE_LOG)
    _USAGE_LOG.clear()
    return out


def set_client(client) -> None:
    """Inject a client (e.g. ScriptedLLM) for tests / offline runs."""
    global _CLIENT
    _CLIENT = client


def reset_client() -> None:
    global _CLIENT
    _CLIENT = None


def get_client():
    global _CLIENT
    if _CLIENT is None:
        _CLIENT = AnthropicClient()
    return _CLIENT


class AnthropicClient:
    """Real model client. Lazy-imports the SDK so offline runs never need it."""

    def __init__(self, max_tokens: int = 4096):
        try:
            from anthropic import Anthropic
        except ImportError as e:  # pragma: no cover
            raise RuntimeError(
                "anthropic SDK not installed. `pip install anthropic`, set "
                "ANTHROPIC_API_KEY, or run with --fake for an offline scripted run."
            ) from e
        self._client = Anthropic()  # reads ANTHROPIC_API_KEY from env
        self.max_tokens = max_tokens

    def complete(self, prompt: str, tier: str, node_id: str | None = None) -> tuple[str, dict]:
        model = _MODELS[tier]
        resp = self._client.messages.create(
            model=model,
            max_tokens=self.max_tokens,
            messages=[{"role": "user", "content": prompt}],
        )
        text = "".join(block.text for block in resp.content if getattr(block, "type", "") == "text")
        usage = {
            "model": model,
            "input_tokens": getattr(resp.usage, "input_tokens", 0),
            "output_tokens": getattr(resp.usage, "output_tokens", 0),
        }
        return text, usage


_FENCE = re.compile(r"^```(?:json)?\s*|\s*```$", re.MULTILINE)


def parse_json(text: str) -> dict:
    """Strip code fences, isolate the outermost JSON object, parse it."""
    cleaned = _FENCE.sub("", text).strip()
    start, end = cleaned.find("{"), cleaned.rfind("}")
    if start == -1 or end == -1 or end < start:
        raise ValueError(f"no JSON object found in model output: {cleaned[:120]!r}")
    snippet = cleaned[start: end + 1]
    try:
        return json.loads(snippet)
    except json.JSONDecodeError as e:
        raise ValueError(f"invalid JSON in model output: {e}") from e


def call_node(node_id: str, tier: str, **vars) -> dict:
    """Render the node's prompt, call the model, return parsed JSON."""
    prompt = load_prompt(node_id, **vars)
    client = get_client()
    text, usage = client.complete(prompt, tier, node_id=node_id)
    record_usage(node_id, tier, usage)
    try:
        return parse_json(text)
    except ValueError as e:
        retry_prompt = (
            prompt
            + f"\n\nYOUR PREVIOUS OUTPUT WAS NOT VALID JSON ({e}). "
            "Return ONLY the JSON object, with no surrounding prose or fences."
        )
        text2, usage2 = client.complete(retry_prompt, tier, node_id=node_id)
        record_usage(node_id, tier, usage2)
        return parse_json(text2)  # raises if still invalid
