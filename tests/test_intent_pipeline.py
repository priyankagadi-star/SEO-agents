"""Intent governance wired through both pipelines: the audit catches an
off-intent page, and a governed content run blocks a draft that trespasses /
omits delegated links (the 'would have caught everything' proof)."""
import pytest

import nodes.audit.a0_intake as a0
from graphs.audit_graph import build_audit_graph
from tools.fetch import parse_html

# A commercial feature URL written as an explainer — the session's off-intent failure.
OFF_INTENT_FEATURE = """<html><head>
<title>Brand Monitoring Platform | Siftly</title>
<meta name="viewport" content="width=device-width, initial-scale=1">
<link rel="canonical" href="https://siftly.ai/brand-monitoring">
</head><body>
<h1>Brand monitoring platform</h1>
<p>Brand monitoring is the practice of tracking mentions of your brand. In this
article we explain the concept, its history, and why it matters in general terms.</p>
<h2>The history of brand monitoring</h2><p>It began decades ago...</p>
<h2>Why awareness matters</h2><p>Awareness is important in general...</p>
</body></html>"""


@pytest.fixture
def fetch_off_intent(monkeypatch):
    monkeypatch.setattr(a0, "fetch_rendered",
                        lambda url: parse_html(OFF_INTENT_FEATURE, url))


def test_audit_flags_off_intent_feature_page(fetch_off_intent):
    result = build_audit_graph().invoke(
        {"url": "https://siftly.ai/brand-monitoring", "primary_query": "brand monitoring tool"})
    intent = result["intent_findings"]
    assert intent["delivered_intent"] == "informational"   # explainer detected
    assert intent["intent_match"] == "drifted"
    assert intent["score_0_2"] == 0
    d = result["diagnosis"]
    assert d["scorecard"]["intent_fit"] == 0
    assert any("off-intent" in r or "off intent" in r for r in d["root_causes"])
    # the contract rides along on the diagnosis (the seam grows)
    assert d["intent_contract"]["primary_intent_type"] == "commercial"


def test_audit_emits_intent_contract_with_template_sections(fetch_off_intent):
    result = build_audit_graph().invoke({"url": "https://siftly.ai/brand-monitoring"})
    contract = result["diagnosis"]["intent_contract"]
    assert contract["page_type"] == "feature"   # classified from the page
    assert "owned_intent_types" in contract and "delegated_query_classes" in contract


def governed_content_state():
    from state import new_content_state
    return new_content_state(
        mode="rebuild", page_type="feature",
        target_url="https://siftly.ai/brand-monitoring",
        primary_keyword="ai brand monitoring",
        research_dossier={}, brand_assets={"author": {"name": "A. Lee"}},
        audience="B2B",
        canonical_sources=["https://siftly.ai/features"],
        gap_entity_matrix={"missing_entities": [], "missing_subtopics": [],
                           "competitor_advantages": []},
        keep_list=[],
        # cluster_map with siblings owning other intents → delegated links required
        cluster_map={
            "spokes": [
                {"url": "https://siftly.ai/brand-monitoring", "intent": "ai brand monitoring",
                 "keywords": ["brand monitoring", "citation share"]},
                {"url": "https://siftly.ai/best-ai-visibility-tools",
                 "intent": "best ai visibility tools",
                 "keywords": ["how to choose", "best tools", "comparison"]},
            ],
        },
        head_queries=[{"query": "real-time brand monitoring", "impressions": 900},
                      {"query": "track competitors across ai engines", "impressions": 600}],
    )


def test_governed_run_blocks_when_delegated_link_missing():
    """The scripted draft never links the sibling 'best tools' URL, so the
    Intent-Fit gate blocks it and the capped route-back escalates — exactly the
    cannibalization/intent failure the gate exists to stop."""
    from langgraph.checkpoint.memory import MemorySaver

    from fakes import ScriptedLLM, make_rebuild_script
    from graphs.content_graph import build_content_graph
    from llm import reset_client, set_client
    from state import EscalateToHuman

    set_client(ScriptedLLM(make_rebuild_script(poison_first_pass=False)))
    try:
        graph = build_content_graph(checkpointer=MemorySaver())
        with pytest.raises(EscalateToHuman):
            graph.invoke(governed_content_state(),
                         config={"configurable": {"thread_id": "governed"}, "recursion_limit": 100})
    finally:
        reset_client()


def test_single_page_run_unaffected_by_governance():
    """No cluster_map + no GSC ⇒ ungoverned ⇒ the intent gates are no-ops and
    the run completes exactly as before."""
    from langgraph.checkpoint.memory import MemorySaver

    from fakes import ScriptedLLM, make_rebuild_script
    from graphs.content_graph import build_content_graph
    from llm import reset_client, set_client
    from state import new_content_state

    state = new_content_state(
        mode="rebuild", page_type="feature",
        target_url="https://siftly.ai/chatgpt-visibility",
        primary_keyword="chatgpt visibility tracking",
        research_dossier={}, brand_assets={"author": {"name": "A. Lee"}},
        audience="B2B", canonical_sources=["https://siftly.ai/features"],
        gap_entity_matrix={"missing_entities": [], "missing_subtopics": [],
                           "competitor_advantages": []},
        keep_list=["Sample Variance differentiator"])
    set_client(ScriptedLLM(make_rebuild_script(poison_first_pass=False)))
    try:
        result = build_content_graph(checkpointer=MemorySaver()).invoke(
            state, config={"configurable": {"thread_id": "ungoverned"}, "recursion_limit": 100})
    finally:
        reset_client()
    assert result["critic_report"]["verdict"] == "pass"
    assert result["intent_contract"]["governed"] is False
