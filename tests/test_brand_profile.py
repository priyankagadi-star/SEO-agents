"""Brand kit (brand_profile) — scaffold, load, and flow to the strategist."""
import json

import pytest

from workspaces import add_account, load_account


@pytest.fixture(autouse=True)
def isolated(tmp_path, monkeypatch):
    monkeypatch.setenv("SEO_WORKSPACES_DIR", str(tmp_path / "workspaces"))


def test_add_account_scaffolds_brand_profile():
    root = add_account("example.com")
    bp = json.loads((root / "brand_profile.json").read_text())
    # the selling-brief shape exists for the owner to fill
    for k in ("value_props", "features", "icp", "objections", "competitors", "cta"):
        assert k in bp


def test_load_account_round_trips_brand_profile():
    root = add_account("example.com")
    (root / "brand_profile.json").write_text(json.dumps({
        "name": "Siftly", "one_liner": "Measure AI visibility",
        "value_props": ["see where AI cites you"],
        "features": [{"name": "Sample Variance", "what_it_does": "stabilizes the score"}],
        "objections": [{"objection": "is this just monitoring?", "response": "no, it scores citation share"}],
    }))
    acc = load_account("example.com")
    assert acc.brand_profile["name"] == "Siftly"
    assert acc.content_inputs()["brand_profile"]["features"][0]["name"] == "Sample Variance"


def test_brand_profile_reaches_strategist_prompt():
    """c7 must pass brand_profile into its prompt (real LLM sell-side input)."""
    from llm import reset_client, set_client
    from fakes import ScriptedLLM, make_rebuild_script
    import nodes.content.c7_strategist as c7

    captured = {}

    class Spy(ScriptedLLM):
        def complete(self, prompt, tier, node_id=None):
            if node_id == "c7_strategist":
                captured["prompt"] = prompt
            return super().complete(prompt, tier, node_id)

    set_client(Spy(make_rebuild_script()))
    try:
        c7.run({
            "mode": "rebuild", "primary_keyword": "ai brand monitoring", "audience": "B2B",
            "facts_ledger": [], "gap_entity_matrix": {}, "keep_list": [], "failure_modes": [],
            "brand_assets": {}, "research_dossier": {},
            "brand_profile": {"value_props": ["real-time citation share"],
                              "features": [{"name": "Sample Variance"}]},
            "intent_contract": {},
        })
    finally:
        reset_client()
    assert "real-time citation share" in captured["prompt"]
    assert "Sample Variance" in captured["prompt"]
