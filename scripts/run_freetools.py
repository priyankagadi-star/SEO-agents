"""Run free-tool pages through the agentic pipeline, sequentially, hands-off.

NEW pages: contract requires seed + research (provided in the inputs). GOAL gate
enforced (depth required). Output: scorecard alongside the per-page artifacts.
Usage: python scripts/run_freetools.py [slug...]
"""
import json, os, re, subprocess, sys
from pathlib import Path
sys.path.insert(0, str(Path.cwd()))

JOBS = [
    "freetool-competitor-comparison",  # priority #1: shareable
    "freetool-product-readiness",      # priority #2: KD-low Shopify
    "freetool-geo-content-grader",     # priority #3: shows the product
]
want = set(sys.argv[1:])
if want:
    JOBS = [j for j in JOBS if j in want]

RUNS = Path("brands/siftly.ai/runs")
SCORE = Path("brands/siftly.ai/inputs/batch/_freetools_scorecard.json")
card = json.loads(SCORE.read_text()) if SCORE.exists() else []

def run_ids():
    return {p.name for p in RUNS.iterdir() if p.is_dir()}

for slug in JOBS:
    inp = f"brands/siftly.ai/inputs/batch/{slug}.json"
    print(f"\n=== {slug} (NEW free-tool, seed+research, GOAL enforced) ===", flush=True)
    before = run_ids()
    env = {**os.environ, "GOAL_ENFORCE": "1"}
    r = subprocess.run([sys.executable, "run.py", "content", "--mode", "net_new",
                        "--account", "siftly.ai", "--inputs", inp],
                       capture_output=True, text=True, env=env)
    out = (r.stdout or "") + (r.stderr or "")
    m = re.search(r"runs/(\d{8}T\d{6}Z)", out)
    new = sorted(run_ids() - before)
    rid = m.group(1) if m else (new[-1] if new else None)
    c = re.search(r"input contract ok — (\w+) page", out)
    ok = bool(rid) and Path(RUNS, rid, "package_out.json").exists() if rid else False
    rec = {"slug": slug, "run": rid, "contract": c.group(1) if c else "?", "ok": ok}
    if not ok:
        rec["tail"] = out[-500:]
    print(f"  -> run={rid} contract={rec['contract']} ok={ok}", flush=True)
    card = [x for x in card if x["slug"] != slug] + [rec]
    SCORE.write_text(json.dumps(card, indent=2))
print("\nFREE-TOOL BATCH DONE", flush=True)
