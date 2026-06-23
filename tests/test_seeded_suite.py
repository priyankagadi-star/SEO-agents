"""The 6 seeded poisons run against the real guardrails (BUILD-SPEC §9 safety
half). No gold files, no model calls. This is the hard GO/KILL gate."""
import eval.seeded_errors as se
from eval.run_eval import main as eval_main


def test_all_six_poisons_caught():
    suite = se.run_seeded_suite()
    assert suite["passed"], [r for r in suite["results"] if not r["caught"]]
    assert suite["caught"] == 6 and suite["total"] == 6
    assert {r["id"] for r in suite["results"]} == {1, 2, 3, 4, 5, 6}


def test_each_seed_reports_evidence():
    for r in se.run_seeded_suite()["results"]:
        assert r["caught"] is True
        assert r["evidence"] and "NOT CAUGHT" not in r["evidence"]


def test_suite_is_a_real_gate_not_a_rubber_stamp(monkeypatch):
    """If a guardrail stopped catching its poison, the suite must fail — proving
    it actually exercises the mechanism."""
    monkeypatch.setitem(se._CHECKS, 1, lambda: (False, "guardrail disabled"))
    suite = se.run_seeded_suite()
    assert suite["passed"] is False and suite["caught"] == 5


def test_eval_exits_zero_with_no_gold(capsys):
    # safety 6/6 + no gold supplied → GO (quality not scored, does not block)
    assert eval_main() == 0
    out = capsys.readouterr().out
    assert "6/6" in out and "not scored" in out and "GO" in out
