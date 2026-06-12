"""Phase 4 acceptance: cold mode (net_new from a seed keyword, no live page)
plus the L4-L6 constraint nodes (c14, c15, c17, c20, c21)."""
import json

import pytest

from fakes import ScriptedLLM, make_cold_script, make_rebuild_script
from graphs.content_graph import build_content_graph
from llm import reset_client, set_client
from state import new_content_state


def cold_state():
    inputs = json.load(open("eval/fixtures/inputs-cold.json"))
    dossier = {"business_context": inputs["business_context"]}
    return new_content_state(
        mode="net_new",
        page_type=inputs["page_type"],
        primary_keyword=inputs["seed_keyword"],
        research_dossier=dossier,
        brand_assets=inputs["brand_assets"],
        audience=inputs["audience"],
        canonical_sources=inputs["canonical_sources"],
    )


@pytest.fixture
def cold_result():
    from langgraph.checkpoint.memory import MemorySaver
    set_client(ScriptedLLM(make_cold_script()))
    try:
        graph = build_content_graph(checkpointer=MemorySaver())
        yield graph.invoke(cold_state(),
                           config={"configurable": {"thread_id": "cold"},
                                   "recursion_limit": 100})
    finally:
        reset_client()


def test_cold_run_completes_with_package(cold_result):
    pkg = cold_result["package_out"]
    assert pkg["full_copy"]
    assert len(pkg["title_variants"]) == 3
    assert cold_result["critic_report"]["verdict"] == "pass"


def test_comparison_judge_skipped_in_cold_mode(cold_result):
    assert cold_result["comparison_report"]["verdict"] == "skipped"


def test_no_fabricated_volumes(cold_result):
    cluster = cold_result["keyword_cluster"]
    assert len(cluster) >= 5  # seed + PAA terms from the fixture
    assert all(c["volume"] == "unknown" and c["kd"] == "unknown" for c in cluster)
    assert cold_result["serp_analysis"]["confidence"] == "stub"


def test_serp_landscape_targets(cold_result):
    targets = cold_result["serp_feature_targets"]
    assert "people_also_ask" in targets and "aio_citation" in targets
    assert cold_result["serp_analysis"]["dominant_format"] in (
        "guide", "blog-listicle", "comparison", "glossary")


def test_competitor_gap_is_stub_labeled_not_fetched(cold_result):
    # stub SERP -> gaps from titles only, competitor URLs recorded, nothing invented
    gap = cold_result["gap_entity_matrix"]
    assert gap["missing_subtopics"]
    assert gap["competitor_advantages"] == []   # no fetches against fixture URLs
    assert len(cold_result["competitors"]) >= 3


def test_unpermissioned_testimonial_never_ships(cold_result):
    """Eval seed 3: permission:false testimonial absent from copy AND schema."""
    quote = "doubled our AI citations"
    assert quote not in cold_result["package_out"]["full_copy"]
    graph = cold_result["schema_jsonld"]["@graph"]
    assert not [b for b in graph if b.get("@type") in ("Review", "AggregateRating")]
    assert any("permission" in h for h in cold_result["human_checkpoints"])


def test_media_manifest_hero_eager_zero_base64(cold_result):
    manifest = cold_result["media_manifest"]
    assert manifest, "expected an overview diagram in the manifest"
    hero = manifest[0]
    assert hero["loading"] == "eager" and hero["fetchpriority"] == "high"
    assert all(not str(m["filename"]).startswith("data:") for m in manifest)
    assert all((m.get("alt") or "").strip() for m in manifest)
    svg = cold_result["svg_assets"][hero["filename"]]
    assert svg.startswith("<svg") and "base64" not in svg


def test_render_critic_passes_on_consistent_copy(cold_result):
    assert cold_result["render_report"]["verdict"] == "pass"


# ---- unit-level checks on the new critics ---------------------------------

def test_render_critic_blocks_missing_enumerated_names():
    from nodes.content.c20_render_critic import run
    state = {
        "brief": {"title_direction": "ok", "meta_direction": "ok", "cta": "Go"},
        "draft": "We cover 4 AI engines (fact:engines-count): ChatGPT and Claude.",
        "media_manifest": [],
        "outline": {"sections": []},
        "facts_ledger": [{
            "id": "engines-count", "claim": "engines",
            "value": "4 (ChatGPT, Claude, Perplexity, Google AI Overviews)",
            "source_url": "x", "verified_by": "c1", "status": "verified",
        }],
    }
    report = run(state)["render_report"]
    assert report["verdict"] == "fail"
    missing = report["failures"][0]["description"]
    assert "Perplexity" in missing and "Google AI Overviews" in missing


def test_comparison_judge_blocks_dropped_entity_keep():
    from nodes.content.c21_comparison_judge import run
    state = {"mode": "rebuild", "draft": "A draft without the differentiator.",
             "lead": " ".join(["w"] * 50),
             "keep_list": ["Sample Variance differentiator"]}
    report = run(state)["comparison_report"]
    assert report["verdict"] == "fail"
    assert report["failures"][0]["severity"] == "blocker"


def test_eeat_only_from_brand_assets():
    from nodes.content.c14_eeat import run
    out = run({"brand_assets": {"testimonials": [
        {"quote": "great", "author": "X", "permission": True},
        {"quote": "fake-ok", "author": "Y", "permission": False},
    ]}, "human_checkpoints": []})
    used = out["_eeat"]["testimonials_used"]
    assert len(used) == 1 and used[0]["author"] == "X"
    assert any("no author" in h for h in out["human_checkpoints"])
    assert any("excluded" in h for h in out["human_checkpoints"])


def test_cannibalization_honest_without_sitemap():
    from nodes.content.c2_cannibalization import run
    out = run({"primary_keyword": "ai citation tracking"})
    assert out["_guardrails"][0]["status"] == "not-checked"
