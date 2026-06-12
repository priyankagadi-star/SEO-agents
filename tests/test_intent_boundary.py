"""intent_boundary_check — the cluster-level sibling of fact_diff (host→link).

Includes the worked demonstration the proposal asked for: build a Siftly
cluster map, run the gate against a brand-monitoring outline, and let the gate
itself produce the host/link (keep/delegate) list.
"""
from cluster_map import ClusterMap
from guardrails import intent_boundary_check

# A realistic Siftly pillar/spoke topology (inferred stand-in — the real
# brand-monitoring gold HTML is an owner-supplied asset still missing).
SIFTLY_CLUSTER = {
    "pillar": {"url": "https://siftly.ai/ai-visibility", "intent": "ai visibility",
               "keywords": ["ai visibility", "generative engine optimization", "geo"]},
    "spokes": [
        {"url": "https://siftly.ai/chatgpt-visibility", "intent": "chatgpt visibility tracking",
         "keywords": ["chatgpt visibility", "track chatgpt", "chatgpt citations"]},
        {"url": "https://siftly.ai/brand-monitoring", "intent": "ai brand monitoring",
         "keywords": ["brand monitoring", "monitor your brand", "citation share"]},
        {"url": "https://siftly.ai/best-ai-visibility-tools", "intent": "best ai visibility tools",
         "keywords": ["how to choose", "best tools", "tool comparison", "buyer's guide"]},
        {"url": "https://siftly.ai/vs-social-listening", "intent": "ai monitoring vs social listening",
         "keywords": ["vs social listening", "versus social listening", "social listening"]},
    ],
}


def test_single_page_mode_is_a_noop():
    outline = {"sections": [{"h2": "Anything goes", "intent": "whatever"}]}
    assert intent_boundary_check(outline, None, page_intent="x") == []
    assert intent_boundary_check(outline, {}, page_intent="x") == []


def test_own_intent_sections_pass():
    cm = ClusterMap.from_config(SIFTLY_CLUSTER)
    outline = {"sections": [
        {"h2": "How Siftly monitors your brand", "intent": "ai brand monitoring"},
        {"h2": "Understanding citation share", "intent": "citation share"},
    ]}
    viols = intent_boundary_check(outline, cm, page_intent="ai brand monitoring",
                                  current_url="https://siftly.ai/brand-monitoring")
    assert viols == []


def test_trespassing_sections_are_blocked():
    """The brand-monitoring page must NOT host 'how to choose' or 'vs social
    listening' — siblings own those intents."""
    cm = ClusterMap.from_config(SIFTLY_CLUSTER)
    outline = {"sections": [
        {"h2": "How Siftly monitors your brand", "intent": "ai brand monitoring"},
        {"h2": "How to choose a brand monitoring tool", "intent": "best tools buyer's guide"},
        {"h2": "Brand monitoring vs social listening", "intent": "versus social listening"},
    ]}
    viols = intent_boundary_check(outline, cm, page_intent="ai brand monitoring",
                                  current_url="https://siftly.ai/brand-monitoring")
    details = " ".join(v.detail for v in viols)
    assert len(viols) == 2
    assert all(v.kind == "intent_trespass" and v.severity == "blocker" for v in viols)
    assert "best-ai-visibility-tools" in details      # "how to choose" delegated
    assert "vs-social-listening" in details           # comparison delegated


def test_unowned_intent_is_allowed_to_host():
    cm = ClusterMap.from_config(SIFTLY_CLUSTER)
    outline = {"sections": [{"h2": "A genuinely novel angle nobody owns",
                             "intent": "prompt-level variance methodology"}]}
    assert intent_boundary_check(outline, cm, page_intent="ai brand monitoring") == []


def test_cluster_map_matching_threshold():
    cm = ClusterMap.from_config(SIFTLY_CLUSTER)
    # a single incidental word must not trigger a false ownership match
    assert cm.match("our tools help you grow") is None
    # a real phrase does
    assert cm.match("how to choose the right platform").intent == "best ai visibility tools"


def test_demonstration_prints_keep_delegate_list(capsys):
    """The gate produces the cut/keep list itself (the proposal's #2)."""
    cm = ClusterMap.from_config(SIFTLY_CLUSTER)
    proposed = [
        {"h2": "How Siftly monitors your brand across AI engines", "intent": "ai brand monitoring"},
        {"h2": "Reading your citation share dashboard", "intent": "citation share"},
        {"h2": "How to choose a brand monitoring tool", "intent": "best tools buyer's guide"},
        {"h2": "Brand monitoring vs social listening", "intent": "versus social listening"},
        {"h2": "Why prompt-level sampling matters", "intent": "sample variance methodology"},
    ]
    page_url = "https://siftly.ai/brand-monitoring"
    viols = intent_boundary_check({"sections": proposed}, cm, "ai brand monitoring", page_url)
    trespass_labels = {v.detail.split("'")[1] for v in viols}
    keep = [s["h2"] for s in proposed if s["h2"] not in trespass_labels]
    delegate = [s["h2"] for s in proposed if s["h2"] in trespass_labels]
    assert "How to choose a brand monitoring tool" in delegate
    assert "Brand monitoring vs social listening" in delegate
    assert "How Siftly monitors your brand across AI engines" in keep
    assert "Why prompt-level sampling matters" in keep   # novel intent, hosted
