"""GO/KILL eval gate (BUILD-SPEC §9), in two independent halves:

1. SAFETY — the 6 seeded poisons run against the real guardrails. No gold files,
   no model calls. This is the hard gate: if any poison ships, the run fails.
2. QUALITY — the rubric scores a candidate package vs a gold package, when one is
   supplied. Gold is the OWNER's QA reference for specific pages — optional, not a
   structural dependency. With no gold, quality is reported as "not scored" and
   does not block the safety verdict.

Exit 0 iff the safety suite is 6/6 AND (no gold supplied OR the candidate scores
≥ rubric_pass_pct% of the gold's score on the same rubric).
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

import yaml

from eval.rubric import passes_vs_gold, score_output
from eval.seeded_errors import run_seeded_suite

GOLD_DIR = Path(__file__).parent / "gold"
_CFG = yaml.safe_load((Path(__file__).parent.parent / "config.yaml").read_text())


def _load_gold_pair():
    """A gold pair is two package_out JSON files in eval/gold/:
       *.gold.json   (the known-good reference) and *.candidate.json (what to grade).
    Returns (candidate, gold) dicts or (None, None) if not supplied. Generic —
    point it at ANY page you want to QA, not specific Siftly files."""
    golds = sorted(GOLD_DIR.glob("*.gold.json"))
    cands = sorted(GOLD_DIR.glob("*.candidate.json"))
    if not golds or not cands:
        return None, None
    return json.loads(cands[0].read_text()), json.loads(golds[0].read_text())


def main() -> int:
    print("=" * 64)
    print("EVAL — GO/KILL gate")
    print("=" * 64)

    # 1. SAFETY (always runs)
    suite = run_seeded_suite()
    print(f"\nSafety suite — seeded poisons caught: {suite['caught']}/{suite['total']}")
    for r in suite["results"]:
        mark = "✓" if r["caught"] else "✗ SHIPPED"
        print(f"  [{mark}] seed {r['id']} {r['name']}: {r['evidence'][:80]}")
    safety_ok = suite["passed"]

    # 2. QUALITY (only when a gold pair is supplied)
    candidate, gold = _load_gold_pair()
    if gold is None:
        print("\nQuality rubric — not scored (no gold pair in eval/gold/).")
        print("  Drop <name>.gold.json + <name>.candidate.json to grade quality vs a")
        print("  known-good page. Optional owner QA; does not block the safety gate.")
        quality_ok = True  # not supplied → does not block
        quality_scored = False
    else:
        pass_pct = _CFG.get("rubric_pass_pct", 85)
        cand_score = score_output(candidate, candidate.get("_state", {}))
        gold_score = score_output(gold, gold.get("_state", {}))
        quality_ok = passes_vs_gold(cand_score, gold_score, pass_pct)
        quality_scored = True
        print(f"\nQuality rubric — candidate {cand_score['total']}/{gold_score['max']} "
              f"vs gold {gold_score['total']} (need ≥{pass_pct}% of gold)")
        print(f"  items: {cand_score['items']}")
        print(f"  verdict: {'PASS' if quality_ok else 'FAIL'}")

    go = safety_ok and quality_ok
    print("\n" + "=" * 64)
    print(f"VERDICT: {'GO (exit 0)' if go else 'KILL (exit 1)'}  "
          f"[safety {'pass' if safety_ok else 'FAIL'}"
          f"{'' if quality_scored else ', quality not scored'}"
          f"{'' if not quality_scored else (', quality ' + ('pass' if quality_ok else 'FAIL'))}]")
    if not safety_ok:
        print("A poison shipped — STOP and fix guardrails before anything else (BUILD-SPEC §9).")
    print("=" * 64)
    return 0 if go else 1


if __name__ == "__main__":
    sys.exit(main())
