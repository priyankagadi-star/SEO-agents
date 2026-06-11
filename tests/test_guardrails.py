"""BUILD-SPEC §6 mandatory guardrail cases — all from real failures in this project."""
import pytest

from guardrails import (
    Violation,
    canonical_verify,
    fact_diff,
    flag_dont_fill,
    grounding_check,
    quantifier_check,
    source_precedence,
)
from ledger import FactsLedger

ENGINES_PATTERN = r"(\d+|zero|one|two|three|four|five|six|seven|eight|nine|ten)\s+(?:major\s+)?AI engines"
WAU_PATTERN = r"(\d[\d,.]*\s*(?:million|billion))\s+weekly"


def ledger_with_engines_4() -> FactsLedger:
    led = FactsLedger()
    led.add({
        "id": "engines-count",
        "claim": "Number of AI engines monitored",
        "value": "4 (ChatGPT, Claude, Perplexity, Google AI Overviews)",
        "source_url": "https://siftly.ai/features",
        "verified_by": "c1_source_reconciler",
        "status": "verified",
        "claim_pattern": ENGINES_PATTERN,
    })
    return led


def ledger_with_chatgpt_wau() -> FactsLedger:
    led = FactsLedger()
    led.add({
        "id": "chatgpt-wau",
        "claim": "ChatGPT weekly active users",
        "value": "900 million (OpenAI, Feb 2026)",
        "source_url": "https://openai.com/blog",
        "verified_by": "c13_evidence",
        "status": "verified",
        "claim_pattern": WAU_PATTERN,
    })
    return led


# 1. fact_diff catches "nine AI engines" when ledger locks engines-count=4
def test_fact_diff_catches_nine_engines():
    led = ledger_with_engines_4()
    draft = "Siftly tracks your brand across nine AI engines, updated daily."
    violations = fact_diff(draft, led)
    assert any(v.kind == "fact_contradiction" for v in violations)
    assert all(v.severity == "blocker" for v in violations if v.kind == "fact_contradiction")


def test_fact_diff_passes_correct_engine_count():
    led = ledger_with_engines_4()
    draft = "Siftly tracks your brand across 4 AI engines (fact:engines-count)."
    assert fact_diff(draft, led) == []


# 2. fact_diff catches "200 million weekly" when locked = 900 million
def test_fact_diff_catches_wrong_wau():
    led = ledger_with_chatgpt_wau()
    draft = "ChatGPT now has 200 million weekly active users."
    violations = fact_diff(draft, led)
    assert any(v.kind == "fact_contradiction" for v in violations)


def test_fact_diff_passes_correct_wau():
    led = ledger_with_chatgpt_wau()
    draft = "ChatGPT now has 900 million weekly active users (fact:chatgpt-wau)."
    assert fact_diff(draft, led) == []


# 3. flag_dont_fill: unflagged stat vs [VERIFY]-flagged stat
def test_flag_dont_fill_catches_unflagged_stat():
    led = FactsLedger()  # empty
    text = "Today, 67% of enterprise teams report AI-driven traffic loss."
    violations = flag_dont_fill(text, led)
    assert any(v.kind == "unsourced_number" and "67%" in v.detail for v in violations)


def test_flag_dont_fill_passes_verify_flagged_stat():
    led = FactsLedger()
    text = "[VERIFY: 67% of enterprise teams — needs a citable source] report AI-driven traffic loss."
    assert flag_dont_fill(text, led) == []


def test_flag_dont_fill_passes_ledger_supported_number():
    led = ledger_with_engines_4()
    text = "Coverage spans 4 million indexed prompts."  # 4 is in ledger... but 4 million is not
    # "4 million" normalizes to 4_000_000 which the ledger does NOT support
    violations = flag_dont_fill(text, led)
    assert any(v.kind == "unsourced_number" for v in violations)


# 4. grounding_check rejects a differentiator with no (fact:…) ref
def test_grounding_check_rejects_unreferenced_claim():
    led = ledger_with_engines_4()
    claims = ["We are the only platform with per-prompt sample variance analysis."]
    violations = grounding_check(claims, led)
    assert any(v.kind == "ungrounded_claim" for v in violations)


def test_grounding_check_rejects_unverified_ref():
    led = FactsLedger()
    claims = ["We monitor more engines than anyone (fact:engines-count)."]
    violations = grounding_check(claims, led)
    assert any(v.kind == "unverified_fact_ref" for v in violations)


def test_grounding_check_accepts_verified_ref():
    led = ledger_with_engines_4()
    claims = ["We monitor 4 AI engines (fact:engines-count)."]
    assert grounding_check(claims, led) == []


# 5. quantifier_check flags "across every AI engine" with engines-count=4
def test_quantifier_check_flags_every():
    led = ledger_with_engines_4()
    text = "Siftly measures brand visibility across every AI engine on the market."
    violations = quantifier_check(text, led)
    assert any(v.kind == "unsupported_quantifier" for v in violations)


def test_quantifier_check_passes_with_fact_ref():
    led = ledger_with_engines_4()
    text = "Siftly covers all 4 major engines (fact:engines-count) in one dashboard."
    assert quantifier_check(text, led) == []


# 6. source_precedence never returns an auto-pick
def test_source_precedence_never_auto_picks():
    conflict = {
        "fact_id": "engines-count",
        "options": [
            {"value": "6", "source_url": "https://siftly.ai/", "source_class": "marketing"},
            {"value": "4", "source_url": "https://siftly.ai/features", "source_class": "feature_page"},
        ],
    }
    precedence = ["owner", "docs", "feature_page", "marketing", "audit"]
    result = source_precedence(conflict, precedence)
    assert result["action"] == "surface"
    assert len(result["options"]) == 2
    assert result["recommended"]["value"] == "4"  # feature_page outranks marketing
    assert "resolved" not in result
    assert result["action"] != "resolve"


# canonical_verify behavior pinning
def test_canonical_verify_verified():
    sources = {"https://siftly.ai/features": "Siftly monitors 4 AI engines: ChatGPT, Claude, Perplexity and Google AI Overviews."}
    assert canonical_verify("monitors 4 AI engines", sources) == "verified"


def test_canonical_verify_conflict():
    sources = {"https://siftly.ai/": "Track your brand across 6 AI engines with Siftly."}
    assert canonical_verify("monitors 4 AI engines", sources) == "conflict"


def test_canonical_verify_unverified():
    sources = {"https://siftly.ai/pricing": "Plans start small and scale with your team."}
    assert canonical_verify("monitors 4 AI engines", sources) == "unverified"


def test_canonical_verify_word_numbers_normalized():
    sources = {"https://siftly.ai/features": "Siftly monitors four AI engines out of the box."}
    assert canonical_verify("monitors 4 AI engines", sources) == "verified"
