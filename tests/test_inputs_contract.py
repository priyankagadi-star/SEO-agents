"""The input contract: a page can't be generated from nothing."""
from inputs_contract import classify_page_state, validate_content_inputs


def test_existing_page_requires_url_and_gsc():
    # rebuild with URL + GSC -> ok
    st, errs = validate_content_inputs(mode="rebuild", seed_keyword=None,
        target_url="https://x.com/p", gsc_available=True, semrush_available=False,
        research_dossier={})
    assert st == "existing" and errs == []
    # rebuild missing GSC -> blocked
    st, errs = validate_content_inputs(mode="rebuild", seed_keyword=None,
        target_url="https://x.com/p", gsc_available=False, semrush_available=False,
        research_dossier={})
    assert st == "existing" and any("GSC" in e for e in errs)
    # missing URL -> blocked
    _, errs = validate_content_inputs(mode="rebuild", seed_keyword=None,
        target_url=None, gsc_available=True, semrush_available=False, research_dossier={})
    assert any("URL" in e for e in errs)


def test_new_page_requires_seed_and_research():
    # net_new with seed + export research -> ok
    st, errs = validate_content_inputs(mode="net_new", seed_keyword="ai visibility",
        target_url=None, gsc_available=False, semrush_available=False,
        research_dossier={"market_stats": [{"stat": "x"}]})
    assert st == "new" and errs == []
    # seed but NO research and NO semrush -> blocked
    _, errs = validate_content_inputs(mode="net_new", seed_keyword="ai visibility",
        target_url=None, gsc_available=False, semrush_available=False, research_dossier={})
    assert any("research" in e for e in errs)
    # no seed -> blocked
    _, errs = validate_content_inputs(mode="net_new", seed_keyword=None,
        target_url=None, gsc_available=False, semrush_available=True, research_dossier={})
    assert any("seed" in e for e in errs)
    # semrush available satisfies research
    _, errs = validate_content_inputs(mode="net_new", seed_keyword="x",
        target_url=None, gsc_available=False, semrush_available=True, research_dossier={})
    assert errs == []


def test_netnew_with_url_and_gsc_is_treated_as_existing():
    # an existing page being optimized via net_new + its GSC -> existing contract
    st, errs = validate_content_inputs(mode="net_new", seed_keyword="x",
        target_url="https://x.com/p", gsc_available=True, semrush_available=False,
        research_dossier={"target_url": "https://x.com/p"})
    assert st == "existing" and errs == []


def test_explicit_page_status_overrides():
    assert classify_page_state("net_new", None, False, {"page_status": "existing"}) == "existing"
    assert classify_page_state("rebuild", "u", True, {"page_status": "new"}) == "new"
