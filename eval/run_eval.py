"""GO/KILL eval gate (BUILD-SPEC §9). Exit 0 only if rubric ≥85% AND seeds 6/6."""
from __future__ import annotations

import sys
from pathlib import Path

GOLD_DIR = Path(__file__).parent / "gold"
GOLD_FILES = [
    "siftly-ai-brand-monitoring.html",
    "siftly-chatgpt-visibility.html",
    "chatgpt-visibility-content-package.md",
    "RUNLOG-chatgpt-visibility.md",
]


def main() -> int:
    missing = [f for f in GOLD_FILES if not (GOLD_DIR / f).exists()]
    if missing:
        print("EVAL BLOCKED — gold files missing from eval/gold/ (BUILD-SPEC §9):")
        for f in missing:
            print(f"  - {f}")
        print("These must be supplied by the project owner; they were not in the repo. [VERIFY-WITH-OWNER]")
        return 1
    print("Gold files present. Rubric + seeded-suite execution is the Phase 2 deliverable.")
    return 1  # not green until Phase 2 wires rubric ≥85% and seeds 6/6


if __name__ == "__main__":
    sys.exit(main())
