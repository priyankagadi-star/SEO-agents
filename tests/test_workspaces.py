import json

import pytest
import yaml

from workspaces import (
    WorkspaceError,
    add_account,
    list_accounts,
    load_account,
)


@pytest.fixture(autouse=True)
def isolated_workspaces(tmp_path, monkeypatch):
    monkeypatch.setenv("SEO_WORKSPACES_DIR", str(tmp_path / "workspaces"))
    return tmp_path / "workspaces"


def configure(root, **overrides):
    cfg_path = root / "account.yaml"
    cfg = yaml.safe_load(cfg_path.read_text())
    cfg.update(overrides)
    cfg_path.write_text(yaml.safe_dump(cfg))


def test_add_creates_scaffold(isolated_workspaces):
    root = add_account("example.com")
    assert (root / "account.yaml").exists()
    assert (root / "brand_assets.json").exists()
    assert (root / "gsc").is_dir() and (root / "runs").is_dir()


def test_add_rejects_duplicates_and_bad_domains():
    add_account("example.com")
    with pytest.raises(WorkspaceError, match="already exists"):
        add_account("example.com")
    for bad in ("../evil", "exam ple.com", "", "https://example.com"):
        with pytest.raises(WorkspaceError):
            add_account(bad)


def test_list_accounts():
    assert list_accounts() == []
    add_account("b.com")
    add_account("a.com")
    assert list_accounts() == ["a.com", "b.com"]


def test_load_unknown_account_names_known_ones():
    add_account("known.com")
    with pytest.raises(WorkspaceError, match="known.com"):
        load_account("unknown.com")


def test_load_account_round_trip():
    root = add_account("example.com")
    configure(root, audience="B2B teams",
              canonical_sources=["https://example.com/features"])
    (root / "brand_assets.json").write_text(json.dumps({"differentiators": ["X"]}))
    acc = load_account("example.com")
    assert acc.audience == "B2B teams"
    assert acc.canonical_sources == ["https://example.com/features"]
    assert acc.brand_assets["differentiators"] == ["X"]
    inputs = acc.content_inputs()
    assert inputs["canonical_sources"] == ["https://example.com/features"]


def test_domain_folder_mismatch_rejected():
    root = add_account("example.com")
    configure(root, domain="other.com")
    with pytest.raises(WorkspaceError, match="folder"):
        load_account("example.com")


def test_gsc_api_mode_reserved_not_silent():
    root = add_account("example.com")
    configure(root, gsc={"mode": "api"})
    with pytest.raises(WorkspaceError, match="not implemented"):
        load_account("example.com")
    configure(root, gsc={"mode": "bogus"})
    with pytest.raises(WorkspaceError, match="gsc.mode"):
        load_account("example.com")


def test_latest_gsc_export_picks_newest():
    import time
    root = add_account("example.com")
    acc = load_account("example.com")
    assert acc.latest_gsc_export() is None
    (root / "gsc" / "old.zip").write_bytes(b"old")
    time.sleep(0.01)
    (root / "gsc" / "new.csv").write_bytes(b"new")
    assert load_account("example.com").latest_gsc_export().name == "new.csv"


def test_accounts_are_isolated_per_run(isolated_workspaces):
    """Two accounts run the same pipeline; runs + assets never cross."""
    from langgraph.checkpoint.memory import MemorySaver

    from fakes import ScriptedLLM, make_rebuild_script
    from graphs.content_graph import build_content_graph
    from llm import reset_client, set_client
    from state import new_content_state

    for domain in ("one.com", "two.com"):
        root = add_account(domain)
        configure(root, audience=f"audience of {domain}",
                  canonical_sources=[f"https://{domain}/features"])

    try:
        results = {}
        for domain in ("one.com", "two.com"):
            acc = load_account(domain)
            set_client(ScriptedLLM(make_rebuild_script(poison_first_pass=False)))
            graph = build_content_graph(checkpointer=MemorySaver())
            state = new_content_state(
                mode="rebuild", page_type="feature",
                primary_keyword="chatgpt visibility tracking",
                research_dossier={}, audience=acc.audience,
                brand_assets=acc.brand_assets,
                canonical_sources=acc.canonical_sources,
                gap_entity_matrix={"missing_entities": [], "missing_subtopics": [],
                                   "competitor_advantages": []},
                keep_list=["Sample Variance differentiator"],
            )
            results[domain] = graph.invoke(
                state, config={"configurable": {"thread_id": domain}, "recursion_limit": 100})
        # each run kept its own account's inputs — nothing leaked across
        assert results["one.com"]["canonical_sources"] == ["https://one.com/features"]
        assert results["two.com"]["canonical_sources"] == ["https://two.com/features"]
        assert results["one.com"]["audience"] != results["two.com"]["audience"]
    finally:
        reset_client()
