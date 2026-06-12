"""Phase 5 acceptance: kill a run mid-L3, resume from the SQLite checkpoint,
identical package_out hash on a fixed scripted-LLM run (BUILD-SPEC §11)."""
import hashlib
import json
import sqlite3

import pytest
from langgraph.checkpoint.sqlite import SqliteSaver

from fakes import ScriptedLLM, make_rebuild_script
from graphs.content_graph import build_content_graph
from llm import reset_client, set_client
from state import new_content_state


def rebuild_state():
    return new_content_state(
        mode="rebuild",
        page_type="feature",
        target_url="https://siftly.ai/chatgpt-visibility",
        primary_keyword="chatgpt visibility tracking",
        research_dossier={},
        brand_assets={"author": {"name": "A. Lee", "credentials": "Head of SEO"}},
        audience="B2B SEO leads",
        canonical_sources=["https://siftly.ai/features"],
        gap_entity_matrix={"missing_entities": [], "missing_subtopics": [],
                           "competitor_advantages": []},
        keep_list=["Sample Variance differentiator"],
    )


def package_hash(result: dict) -> str:
    return hashlib.sha256(
        json.dumps(result["package_out"], sort_keys=True).encode()
    ).hexdigest()


def saver(path):
    return SqliteSaver(sqlite3.connect(path, check_same_thread=False))


@pytest.fixture(autouse=True)
def scripted():
    set_client(ScriptedLLM(make_rebuild_script(poison_first_pass=False)))
    yield
    reset_client()


def test_kill_mid_l3_resume_identical_hash(tmp_path):
    cfg = {"configurable": {"thread_id": "resume-test"}, "recursion_limit": 100}

    # reference: uninterrupted run
    ref = build_content_graph(checkpointer=saver(tmp_path / "ref.sqlite")).invoke(
        rebuild_state(), config=cfg)
    ref_hash = package_hash(ref)

    # interrupted run: stream and kill mid-L3 (right after the section drafter)
    db = tmp_path / "killed.sqlite"
    graph = build_content_graph(checkpointer=saver(db))
    seen = []
    for update in graph.stream(rebuild_state(), config=cfg, stream_mode="updates"):
        seen += list(update)
        if "c11_section_drafter" in update:
            break  # simulate the process dying mid-L3
    assert "c11_section_drafter" in seen and "c22_packager" not in seen
    del graph

    # resume: fresh graph + fresh connection to the same checkpoint, input None.
    # the ScriptedLLM is fresh too — exactly like a new process.
    set_client(ScriptedLLM(make_rebuild_script(poison_first_pass=False)))
    resumed = build_content_graph(checkpointer=saver(db)).invoke(None, config=cfg)

    assert resumed["package_out"]["full_copy"]
    assert package_hash(resumed) == ref_hash


def test_resume_does_not_rerun_completed_nodes(tmp_path):
    cfg = {"configurable": {"thread_id": "resume-norerun"}, "recursion_limit": 100}
    db = tmp_path / "ck.sqlite"
    graph = build_content_graph(checkpointer=saver(db))
    for update in graph.stream(rebuild_state(), config=cfg, stream_mode="updates"):
        if "c11_section_drafter" in update:
            break
    del graph

    fresh = ScriptedLLM(make_rebuild_script(poison_first_pass=False))
    set_client(fresh)
    build_content_graph(checkpointer=saver(db)).invoke(None, config=cfg)
    # pre-kill nodes (c1..c11) were not called again after resume
    assert "c1_source_reconciler" not in fresh.counts
    assert "c11_section_drafter" not in fresh.counts
    assert fresh.counts.get("c12_faq", 0) >= 1  # post-kill node ran


def test_runlog_carries_duration_and_cost(tmp_path):
    cfg = {"configurable": {"thread_id": "runlog"}, "recursion_limit": 100}
    result = build_content_graph(checkpointer=saver(tmp_path / "x.sqlite")).invoke(
        rebuild_state(), config=cfg)
    runlog = result["_runlog"]
    assert all("duration_ms" in e and "cost_usd" in e for e in runlog)
    # scripted client reports zero tokens, so cost must be exactly 0
    assert sum(e["cost_usd"] for e in runlog) == 0
    # LLM nodes carry a usage record naming the scripted model
    c7 = next(e for e in runlog if e["node"] == "c7_strategist")
    assert c7["usage"] and c7["usage"][0]["model"] == "scripted-strong"
