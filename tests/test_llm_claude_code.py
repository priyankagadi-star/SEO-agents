"""ClaudeCodeClient — model steps via the local `claude` CLI (no API key).

Pinned against a mocked CLI runner so we never invoke nested claude in tests.
"""
import json

import pytest

from llm import ClaudeCodeClient


def runner_returning(payload, capture, rc=0):
    def run(args, prompt):
        capture.append({"args": args, "prompt": prompt})
        return json.dumps(payload), rc
    return run


def client(payload, capture, rc=0, **kw):
    return ClaudeCodeClient(models={"strong": "claude-sonnet-4-6", "fast": "claude-haiku-4-5"},
                            runner=runner_returning(payload, capture, rc), **kw)


ENVELOPE = {
    "type": "result", "subtype": "success", "is_error": False,
    "result": '{"lead": "An answer-first lead."}',
    "usage": {"input_tokens": 210, "output_tokens": 33},
    "total_cost_usd": 0.0021,
}


def test_completion_parses_result_and_usage():
    seen = []
    text, usage = client(ENVELOPE, seen).complete("prompt body", "fast")
    assert json.loads(text)["lead"] == "An answer-first lead."
    assert usage == {"model": "claude-code:claude-haiku-4-5", "input_tokens": 210, "output_tokens": 33}
    args = seen[0]["args"]
    assert "-p" in args and "--output-format" in args and "json" in args
    assert args[args.index("--model") + 1] == "claude-haiku-4-5"
    assert seen[0]["prompt"] == "prompt body"


def test_tier_maps_to_model_and_tools_disabled():
    seen = []
    client(ENVELOPE, seen).complete("p", "strong")
    args = seen[0]["args"]
    assert args[args.index("--model") + 1] == "claude-sonnet-4-6"
    # tools disabled -> pure completion, never touches the repo
    assert args[args.index("--allowedTools") + 1] == ""


def test_nonzero_exit_raises():
    with pytest.raises(RuntimeError, match="rc=1"):
        client(ENVELOPE, [], rc=1).complete("p", "fast")


def test_is_error_envelope_raises():
    bad = {**ENVELOPE, "is_error": True, "result": "model declined"}
    with pytest.raises(RuntimeError, match="returned an error"):
        client(bad, []).complete("p", "fast")


def test_non_json_envelope_raises():
    def run(args, prompt):
        return "not json at all", 0
    c = ClaudeCodeClient(models={"fast": "x"}, runner=run)
    with pytest.raises(RuntimeError, match="did not return JSON"):
        c.complete("p", "fast")


def test_call_node_routes_through_claude_code(monkeypatch):
    """End-to-end: call_node uses the injected ClaudeCodeClient and records usage."""
    import llm
    seen = []
    llm.set_client(client(ENVELOPE, seen))
    try:
        out = llm.call_node("c10_hook", "fast", primary_keyword="k", unique_insight="",
                            audience="a", brand_voice="{}", ledger_markdown="(empty)")
    finally:
        llm.reset_client()
    assert out["lead"] == "An answer-first lead."
    assert seen and "claude" in seen[0]["args"][0]
