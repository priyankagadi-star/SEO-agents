"""Phase 3 acceptance: audit pipeline a0–a11 + the diagnosis seam."""
import csv
import io
import json
import zipfile

import pytest

import nodes.audit.a0_intake as a0
from graphs.audit_graph import build_audit_graph
from state import validate_diagnosis
from tools.fetch import parse_html
from tools.gsc import parse_gsc_export

WEAK_HTML = """<html><head><title>Siftly — the future of brand intelligence and AI marketing platforms for modern enterprises</title>
<link rel="canonical" href="https://other.example.com/page">
</head><body>
<h1>Welcome</h1><h1>Siftly</h1>
<h4>Our story</h4>
<p>Lorem ipsum dolor sit amet. Acme Corp uses our platform.</p>
<img src="data:image/png;base64,AAAA">
<img src="IMG_1234.png">
</body></html>"""

STRONG_HTML = """<html><head><title>ChatGPT Visibility Tracking for Brands | Siftly</title>
<meta name="description" content="Siftly measures how often ChatGPT cites your brand across four AI engines, with prompt-level Sample Variance analysis.">
<meta name="viewport" content="width=device-width, initial-scale=1">
<link rel="canonical" href="https://siftly.ai/chatgpt-visibility">
<script type="application/ld+json">{"@context":"https://schema.org","@graph":[{"@type":"FAQPage","mainEntity":[{"@type":"Question","name":"What is ChatGPT visibility?","acceptedAnswer":{"@type":"Answer","text":"How often ChatGPT cites your brand."}}]},{"@type":"Person","name":"A. Lee"}]}</script>
</head><body>
<h1>ChatGPT Visibility Tracking</h1>
<p>ChatGPT visibility tracking measures how often ChatGPT recommends your brand when buyers ask questions in 2026. Siftly samples hundreds of prompt phrasings, applies Sample Variance analysis, and reports your citation share across four AI engines so you can act on it. Get started with a free trial today.</p>
<h2>How it works</h2>
<p>By A. Lee. Siftly samples representative prompts across engines and records every brand citation. The variance between phrasings is measured so a single lucky query never inflates your score. Results are aggregated weekly into a citation-share metric your team can track against competitors and improve with content changes.</p>
<h2>FAQ — frequently asked questions</h2>
<p>What is ChatGPT visibility? How often ChatGPT cites your brand.</p>
<img src="dashboard-citation-share.png" alt="Siftly dashboard showing citation share" loading="eager">
<a href="/features">Features</a><a href="/pricing">Pricing</a><a href="/docs">Docs</a><a href="/blog">Blog</a><a href="/about">About</a>
</body></html>"""


@pytest.fixture
def fetch_weak(monkeypatch):
    monkeypatch.setattr(a0, "fetch_rendered",
                        lambda url: parse_html(WEAK_HTML, url))


@pytest.fixture
def fetch_strong(monkeypatch):
    monkeypatch.setattr(a0, "fetch_rendered",
                        lambda url: parse_html(STRONG_HTML, url))


def make_gsc_zip(tmp_path, rows):
    buf = io.StringIO()
    w = csv.writer(buf)
    w.writerow(["Top queries", "Clicks", "Impressions", "CTR", "Position"])
    w.writerows(rows)
    path = tmp_path / "export.zip"
    with zipfile.ZipFile(path, "w") as zf:
        zf.writestr("Queries.csv", buf.getvalue())
    return path


def run_audit(url="https://siftly.ai/chatgpt-visibility", gsc_path=None):
    graph = build_audit_graph()
    state = {"url": url}
    if gsc_path:
        state["gsc_path"] = str(gsc_path)
    return graph.invoke(state)


def test_weak_page_produces_owned_defects(fetch_weak):
    result = run_audit()
    d = result["diagnosis"]
    validate_diagnosis(d)
    assert len(d["defects"]) >= 5
    # every defect names a content node (the seam's whole point)
    assert all(x["owning_step"].startswith("c") for x in d["defects"])
    by_check = " ".join(x["description"] for x in d["defects"])
    assert "placeholder" in by_check        # Acme/lorem caught (blocker)
    assert any(x["severity"] == "blocker" for x in d["defects"])
    assert "canonical" in by_check          # off-site canonical flagged
    assert "h1_count" in by_check           # two H1s


def test_strong_page_scores_well_and_builds_keep_list(fetch_strong):
    result = run_audit()
    d = result["diagnosis"]
    assert d["page_type"] == "feature"
    assert "chatgpt visibility tracking" in d["primary_query"]
    assert len(d["keep_list"]) >= 5
    assert any("answer-first" in k for k in d["keep_list"])
    assert sum(d["scorecard"].values()) >= 12
    assert not any(x["severity"] == "blocker" for x in d["defects"])


def test_honest_degradation_serp_and_authority(fetch_strong):
    result = run_audit()
    assert result["serp_findings"]["confidence"] == "stub"
    assert result["serp_findings"]["score_0_2"] is None
    assert result["authority_findings"]["status"] == "not-assessed"
    # neither fabricates a scorecard entry
    assert "serp" not in result["diagnosis"]["scorecard"]
    assert "authority" not in result["diagnosis"]["scorecard"]


def test_aio_zero_click_rule(fetch_strong, tmp_path):
    gsc = make_gsc_zip(tmp_path, [
        ["chatgpt visibility", 1, 12000, "0.01%", 4.2],   # pos<=10, CTR ~0.008% -> anomaly
        ["ai brand tracking", 50, 1000, "5%", 9.0],
        ["chatgpt brand monitoring", 5, 800, "0.6%", 12.5],  # striking distance
    ])
    result = run_audit(gsc_path=gsc)
    perf = result["performance"]
    assert "structurally suppressed" in perf["aio_flag"]
    assert "chatgpt visibility" in perf["aio_affected_queries"]
    assert "chatgpt brand monitoring" in perf["striking_distance_queries"]
    assert perf["aio_zero_click_share"] > 0.5
    # the flag propagates into the diagnosis root causes
    assert any("zero-click" in r for r in result["diagnosis"]["root_causes"])


def test_gsc_parser_math(tmp_path):
    gsc = make_gsc_zip(tmp_path, [["q", 28, 100, "28%", 1.0]])
    parsed = parse_gsc_export(gsc)
    assert parsed["totals"]["expected_clicks"] == 28.0  # pos-1 curve = 28%
    assert parsed["zero_click_anomaly_score"] == 0.0


def test_seam_audit_to_rebuild_no_hand_edits(fetch_weak, tmp_path):
    """Phase 3 acceptance: run.py audit then content --mode rebuild works
    with no hand edits between the two."""
    from langgraph.checkpoint.memory import MemorySaver

    from fakes import ScriptedLLM, make_rebuild_script
    from graphs.content_graph import build_content_graph
    from llm import reset_client, set_client
    from state import new_content_state

    diagnosis = run_audit()["diagnosis"]
    # serialize + reload exactly as the CLI does
    raw = json.loads(json.dumps(diagnosis))
    validate_diagnosis(raw)

    state = new_content_state(
        mode="rebuild",
        page_type=raw["page_type"],
        target_url=raw["url"],
        primary_keyword=raw["primary_query"],
        research_dossier={},
        brand_assets={"author": {"name": "A. Lee"}},
        audience="B2B",
        canonical_sources=["https://siftly.ai/features"],
        gap_entity_matrix=raw["gap_entity_matrix"],
        keep_list=raw["keep_list"],
        failure_modes=[x["description"] for x in raw["defects"]],
    )
    set_client(ScriptedLLM(make_rebuild_script(poison_first_pass=False)))
    try:
        graph = build_content_graph(checkpointer=MemorySaver())
        result = graph.invoke(state, config={"configurable": {"thread_id": "seam"},
                                             "recursion_limit": 100})
    finally:
        reset_client()
    assert result["package_out"]["full_copy"]
    assert result["failure_modes"]  # the audit's defects drove the rebuild
