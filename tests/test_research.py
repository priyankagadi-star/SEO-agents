"""SemrushProvider — pinned against mocked Analytics API CSV responses."""
import httpx
import pytest

from tools.research import SemrushProvider, _parse_csv

RELATED_CSV = (
    "Keyword;Search Volume;Keyword Difficulty Index;CPC;Competition\n"
    "ai citation tracking;1300;42;5.10;0.45\n"
    "track brand in chatgpt;880;38;4.20;0.40\n"
)
QUESTIONS_CSV = (
    "Keyword;Search Volume\n"
    "how to track ai citations;210\n"
    "what is ai citation tracking;170\n"
)
ORGANIC_CSV = (
    "Domain;Url\n"
    "competitor-one.com;https://competitor-one.com/ai-citation-tracking\n"
    "competitor-two.com;https://competitor-two.com/guide\n"
)


def provider_for(report_csv: dict, capture):
    def handler(request: httpx.Request) -> httpx.Response:
        rtype = request.url.params.get("type")
        capture.append(request.url.params)
        return httpx.Response(200, text=report_csv.get(rtype, ""))
    return SemrushProvider(api_key="k", transport=httpx.MockTransport(handler))


def test_parse_csv_and_error_line():
    assert _parse_csv("A;B\n1;2")[0] == {"A": "1", "B": "2"}
    assert _parse_csv("ERROR 50 :: NOTHING FOUND") == []
    assert _parse_csv("") == []


def test_no_key_is_honest_stub(monkeypatch):
    monkeypatch.delenv("SEMRUSH_API_KEY", raising=False)
    p = SemrushProvider(api_key="")
    assert p.available is False
    r = p.research("ai citation tracking")
    assert r["stub"] is True and r["keywords"] == [] and r["organic"] == []


def test_related_keywords_real_volumes():
    seen = []
    p = provider_for({"phrase_related": RELATED_CSV}, seen)
    kws = p.related_keywords("ai citation tracking")
    assert kws[0]["term"] == "ai citation tracking"
    assert kws[0]["volume"] == 1300 and kws[0]["kd"] == 42.0
    assert seen[0]["type"] == "phrase_related" and seen[0]["key"] == "k"


def test_questions_and_organic():
    p = provider_for({"phrase_questions": QUESTIONS_CSV, "phrase_organic": ORGANIC_CSV}, [])
    assert "how to track ai citations" in p.questions("x")
    comp = p.organic_competitors("x")
    assert comp[0]["url"] == "https://competitor-one.com/ai-citation-tracking"


def test_research_bundle_live():
    p = provider_for({"phrase_related": RELATED_CSV, "phrase_questions": QUESTIONS_CSV,
                      "phrase_organic": ORGANIC_CSV}, [])
    r = p.research("ai citation tracking")
    assert r["stub"] is False and r["source"] == "semrush"
    assert len(r["keywords"]) == 2 and len(r["questions"]) == 2 and len(r["organic"]) == 2


def test_c3_uses_real_volumes_when_keyed():
    from llm import reset_client
    import tools.research as research
    from nodes.content.c3_kw_intent_mapper import run
    research.set_provider(provider_for(
        {"phrase_related": RELATED_CSV, "phrase_questions": QUESTIONS_CSV, "phrase_organic": ORGANIC_CSV}, []))
    try:
        out = run({"mode": "net_new", "primary_keyword": "ai citation tracking"})
    finally:
        research.set_provider(None)
        reset_client()
    cluster = out["keyword_cluster"]
    assert any(c.get("volume") == 1300 for c in cluster)        # real volume, not "unknown"
    assert out["serp_analysis"]["research_source"] == "semrush"
    assert out["_guardrails"][0]["real_volumes"] is True


def test_c3_stub_keeps_volumes_unknown():
    import tools.research as research
    from nodes.content.c3_kw_intent_mapper import run
    research.set_provider(SemrushProvider(api_key=""))   # no key → stub
    try:
        out = run({"mode": "net_new", "primary_keyword": "ai citation tracking"})
    finally:
        research.set_provider(None)
    assert all(c["volume"] == "unknown" for c in out["keyword_cluster"])  # never fabricated
