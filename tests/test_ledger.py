from ledger import FactsLedger, extract_numbers, word_to_number


def make_fact(**over):
    f = {
        "id": "engines-count",
        "claim": "engines monitored",
        "value": "4 (ChatGPT, Claude, Perplexity, Google AI Overviews)",
        "source_url": "https://siftly.ai/features",
        "verified_by": "c1_source_reconciler",
        "status": "verified",
    }
    f.update(over)
    return f


def test_add_and_get():
    led = FactsLedger()
    led.add(make_fact())
    f = led.get("engines-count")
    assert f is not None and f["value"].startswith("4")


def test_add_same_value_is_noop():
    led = FactsLedger()
    led.add(make_fact())
    led.add(make_fact())
    assert len(led) == 1
    assert led.get("engines-count")["status"] == "verified"


def test_add_different_value_creates_conflict_not_overwrite():
    led = FactsLedger()
    led.add(make_fact())
    led.add(make_fact(value="6 engines", source_url="https://siftly.ai/"))
    f = led.get("engines-count")
    assert f["status"] == "conflict"
    assert "4 (ChatGPT, Claude, Perplexity, Google AI Overviews)" in f["conflict_values"]
    assert "6 engines" in f["conflict_values"]
    # original value field is preserved, not overwritten
    assert f["value"].startswith("4")


def test_supports_number():
    led = FactsLedger()
    led.add(make_fact())
    assert led.supports_number("4")
    assert not led.supports_number("9")
    assert not led.supports_number("no numbers here")


def test_supports_number_with_scales():
    led = FactsLedger()
    led.add(make_fact(id="chatgpt-wau", value="900 million (OpenAI, Feb 2026)"))
    assert led.supports_number("900 million")
    assert not led.supports_number("200 million")


def test_conflict_facts_do_not_support_numbers():
    led = FactsLedger()
    led.add(make_fact())
    led.add(make_fact(value="6"))
    assert not led.supports_number("4")  # conflicted facts are not 'verified'


def test_to_markdown():
    led = FactsLedger()
    led.add(make_fact())
    md = led.to_markdown()
    assert "engines-count" in md and "verified" in md
    assert FactsLedger().to_markdown() == "(ledger is empty)"


def test_wraps_external_list_in_place():
    backing: list = []
    led = FactsLedger(backing)
    led.add(make_fact())
    assert len(backing) == 1  # graph state list sees the append


def test_number_helpers():
    assert word_to_number("nine") == 9.0
    assert word_to_number("4") == 4.0
    assert word_to_number("1,200") == 1200.0
    assert word_to_number("engines") is None
    assert 900_000_000.0 in extract_numbers("900 million users")
    assert 4.0 in extract_numbers("four engines")
