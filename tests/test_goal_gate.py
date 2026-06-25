"""GOAL gate — the Information-Gain Score that decides whether a page carries
the measurable value Google rewards. Deterministic; pinned here so the agent
can be graded against a number, not a vibe."""
import json

from guardrails import information_gain_score
from ledger import FactsLedger

# A rich page: external citations, sourced stats, proprietary benchmarks,
# concrete examples, real questions, low brand density, complete author.
RICH_FACTS = [
    {"id": "proof-domu", "claim": "Domu result", "value": "Domu reached #9 within 30 days",
     "status": "verified", "source_url": "study"},
    {"id": "proof-kiwabi", "claim": "KIWABI result", "value": "KIWABI grew revenue 3.5x",
     "status": "verified", "source_url": "benchmark"},
    {"id": "engines", "claim": "engines", "value": "9 engines", "status": "verified",
     "source_url": "brand_profile"},
]
RICH_DRAFT = (
    "AI search referrals rose 40% (fact:engines) per https://semrush.com research. "
    "A 2026 study at https://gartner.com found 60% of buyers (fact:engines) shortlist with AI. "
    "Our own benchmark shows Domu reached #9 (fact:proof-domu) in 30 days. "
    "For example, KIWABI grew 3.5x (fact:proof-kiwabi) revenue month over month. "
    "Such as when a team tracks 9 engines (fact:engines) across regions. "
    "Consider how citation share hit 22% (fact:engines) in 8 weeks for one team. "
    "Independent analysis at https://forrester.com corroborates the shift to AI discovery. "
    "Step 1, audit your visibility; step 2, publish; step 3, measure the revenue impact. "
    "Buyers now ask AI before they ever click a blue link, and the gap compounds weekly."
)
RICH_KW = dict(
    author={"name": "A", "credentials": "Founder", "bio": "Bio here", "linkedin": "https://x"},
    faq=[{"q": f"Q{i} about AI visibility tracking"} for i in range(5)],
    trend_signals=["AI referrals rose per https://semrush.com/report"],
    brand_names=["Acme"],
    owner_domains=["acme.com"],
    threshold=70,
)


def test_rich_page_passes_information_gain():
    r = information_gain_score(RICH_DRAFT, FactsLedger(list(RICH_FACTS)), **RICH_KW)
    assert r.score >= 70, (r.score, {k: v["points"] for k, v in r.metrics.items()})
    assert r.passed
    assert r.metrics["external_citations"]["value"] >= 3
    assert r.metrics["proprietary_data"]["ok"]


def test_thin_brand_heavy_page_fails_and_blocks():
    """A safe-but-thin page: no citations, no data, all self-promotion."""
    draft = ("Acme is the best platform. Acme helps you win. Acme is easy to use. "
             "Acme makes AI visibility simple. Choose Acme today for your team. "
             "Acme is trusted by teams everywhere who love Acme.")
    r = information_gain_score(draft, FactsLedger([]), brand_names=["Acme"],
                              owner_domains=["acme.com"], threshold=70, enforce=True)
    assert r.score < 70 and not r.passed
    kinds = {v.kind for v in r.violations}
    assert "goal_information_gain" in kinds
    assert any(v.severity == "blocker" for v in r.violations)


def test_hard_precondition_value_density_blocks():
    draft = ("This is important to understand. It really matters a lot. "
             "We believe in helping you. Our mission is to serve. "
             "Let us walk through it together now.")  # all restatement, no facts
    r = information_gain_score(draft, FactsLedger([]), brand_names=["X"], enforce=True)
    pre = r.preconditions["distinct_value_density"]
    assert not pre["ok"]
    assert any(v.kind == "goal_precondition:distinct_value_density" for v in r.violations)


def test_hard_precondition_unresolved_verify_blocks():
    r = information_gain_score("We serve [VERIFY: how many] customers.", FactsLedger([]),
                              brand_names=["X"], enforce=True)
    assert not r.preconditions["no_unresolved_verify"]["ok"]
    assert any(v.kind == "goal_precondition:no_unresolved_verify" for v in r.violations)


def test_freshness_requires_sourced_trend():
    owner_asserted = information_gain_score(RICH_DRAFT, FactsLedger(list(RICH_FACTS)),
                                            **{**RICH_KW, "trend_signals": ["AI is growing"]})
    assert not owner_asserted.preconditions["freshness_sourced_trend"]["ok"]


def test_advisory_mode_downgrades_blockers_to_major():
    draft = "Acme is great. Acme is the best. Acme wins."
    r = information_gain_score(draft, FactsLedger([]), brand_names=["Acme"], enforce=False)
    assert r.violations and all(v.severity == "major" for v in r.violations)


def test_thresholds_scale_with_word_budget():
    """A guide (longer budget) demands more data points than a feature page."""
    base = information_gain_score(RICH_DRAFT, FactsLedger(list(RICH_FACTS)),
                                  **{**RICH_KW, "word_budget": [1400, 1800]})
    guide = information_gain_score(RICH_DRAFT, FactsLedger(list(RICH_FACTS)),
                                   **{**RICH_KW, "word_budget": [2000, 3200]})
    assert guide.metrics["sourced_data_points"]["threshold"] > \
        base.metrics["sourced_data_points"]["threshold"]


def test_brand_ratio_penalizes_self_promotion():
    heavy = ("Acme tracks visibility. Acme finds gaps. Acme publishes content. "
             "Acme proves impact. Acme is end to end.")
    r = information_gain_score(heavy, FactsLedger([]), brand_names=["Acme"])
    assert not r.metrics["brand_ratio"]["ok"]


def test_c19_attaches_information_gain_report():
    """The critic always reports the score, even when advisory."""
    import nodes.content.c19_critic as c19
    out = c19.run({"facts_ledger": list(RICH_FACTS), "draft": RICH_DRAFT,
                   "faq": RICH_KW["faq"], "brand_profile": {"name": "Acme"},
                   "brand_assets": {"author": RICH_KW["author"]}})
    ig = out["critic_report"]["information_gain"]
    assert "score" in ig and "metrics" in ig and "preconditions" in ig
