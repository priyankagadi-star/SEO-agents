"""Intent governance v2 — classify_intent, mirror_score, intent_fit_check,
and the mandatory new tests (a)-(d) from the architecture spec."""
from guardrails import (
    Violation,
    classify_intent,
    intent_fit_check,
    mirror_score,
    owned_intent_types,
)


# ---- classify_intent (the load-bearing new function) ----------------------

def test_classify_intent_buckets():
    assert classify_intent("what is ai visibility") == "informational"
    assert classify_intent("how to measure brand mentions") == "informational"
    assert classify_intent("best ai visibility tools") == "commercial"
    assert classify_intent("ai brand monitoring platform") == "commercial"
    assert classify_intent("chatgpt visibility tracker") == "commercial"
    assert classify_intent("siftly vs profound") == "commercial"
    assert classify_intent("how to choose a monitoring tool") == "commercial"  # commercial > info
    assert classify_intent("siftly pricing") == "transactional"
    assert classify_intent("start free trial") == "transactional"
    assert classify_intent("siftly login") == "navigational"


def test_owned_intent_types():
    assert owned_intent_types("feature") == {"commercial", "transactional"}
    assert owned_intent_types("guide") == {"informational"}
    assert owned_intent_types("comparison") == {"commercial", "transactional"}


# ---- mirror_score ----------------------------------------------------------

def test_mirror_score():
    hq = [
        {"term": "real-time brand monitoring", "intent_type": "commercial"},
        {"term": "track multiple competitors", "intent_type": "commercial"},
        {"term": "what is brand monitoring", "intent_type": "informational"},  # ignored
    ]
    good = ("Siftly delivers real-time brand monitoring so you can track "
            "multiple competitors at once across AI engines.")
    assert mirror_score(good, hq) == 1.0
    bad = "Our product helps companies understand their presence in answers."
    assert mirror_score(bad, hq) < 0.6
    assert mirror_score("anything", []) == 1.0  # nothing commercial to mirror


# ---- intent_fit_check governance switch -----------------------------------

def governed_contract(**over):
    c = {
        "governed": True,
        "page_type": "feature",
        "primary_intent_type": "commercial",
        "primary_keyword": "ai brand monitoring",
        "owned_intent_types": ["commercial", "transactional"],
        "delegated_query_classes": {},
        "head_queries": [],
    }
    c.update(over)
    return c


def test_ungoverned_contract_is_noop():
    c = governed_contract(governed=False)
    assert intent_fit_check("anything at all", c, h1="Whatever") == []
    assert intent_fit_check("x", None) == []


# (b) a feature page whose H1 lacks the commercial keyword fails Intent-Fit
def test_h1_missing_keyword_fails():
    c = governed_contract()
    v = intent_fit_check("Real-time monitoring across engines.", c,
                         h1="Understanding Generative Engines")
    assert any(x.kind == "h1_missing_keyword" and x.severity == "blocker" for x in v)
    # H1 that carries it passes that check
    v2 = intent_fit_check("AI brand monitoring in real time.", c,
                          h1="AI Brand Monitoring for Teams")
    assert not any(x.kind == "h1_missing_keyword" for x in v2)


# (d) mirror_score < 0.6 fails the gate
def test_low_mirror_score_fails():
    c = governed_contract(head_queries=[
        {"term": "real-time competitor tracking", "intent_type": "commercial"},
        {"term": "monitor brand across ai engines", "intent_type": "commercial"},
    ])
    drift = "AI Brand Monitoring. We help you grasp your standing in answers."
    v = intent_fit_check(drift, c, h1="AI Brand Monitoring")
    assert any(x.kind == "low_mirror_score" for x in v)


def test_delivered_intent_drift_fails():
    c = governed_contract()
    # an explainer lead on a commercial page → drifts to informational
    draft = "What is brand monitoring? Brand monitoring is the practice of..."
    v = intent_fit_check(draft, c, h1="What is AI Brand Monitoring")
    assert any(x.kind == "intent_drift" for x in v)


def test_missing_delegated_link_fails():
    c = governed_contract(delegated_query_classes={
        "best ai visibility tools": "https://siftly.ai/best-ai-visibility-tools"})
    draft = "AI brand monitoring in real time across engines."  # no link
    v = intent_fit_check(draft, c, h1="AI Brand Monitoring")
    assert any(x.kind == "missing_delegated_link" for x in v)
    draft2 = draft + " See our guide at https://siftly.ai/best-ai-visibility-tools for picks."
    v2 = intent_fit_check(draft2, c, h1="AI Brand Monitoring")
    assert not any(x.kind == "missing_delegated_link" for x in v2)


# (a) a 'what is X' query classifies informational and is delegated by a feature page
def test_informational_query_delegated_from_feature():
    assert classify_intent("what is ai visibility") == "informational"
    assert "informational" not in owned_intent_types("feature")  # so it must delegate
