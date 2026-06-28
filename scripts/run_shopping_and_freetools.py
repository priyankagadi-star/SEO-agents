"""Sequential batch — 5 shopping features + 3 free-tools that died earlier.

NEW pages, contract requires seed + research (each input carries it). GOAL gate
enforced. Writes a scorecard so progress survives interrupts. Designed to be
launched detached (setsid + nohup) so session restarts don't kill it.
Usage: python scripts/run_shopping_and_freetools.py [slug...]
"""
import json, os, re, subprocess, sys, time
from pathlib import Path
sys.path.insert(0, str(Path.cwd()))

JOBS = [
    "shopping-share-of-shelf",            # priority anchor, 210 vol, real Semrush demand
    "shopping-citation-intelligence",     # programmatic
    "shopping-buy-button-ownership",      # programmatic
    "shopping-pricing-intelligence",      # programmatic
    "shopping-competitor-analysis",       # programmatic
    "freetool-competitor-comparison",     # relaunched
    "freetool-product-readiness",         # relaunched
    "freetool-geo-content-grader",        # relaunched
]
want = set(sys.argv[1:])
if want:
    JOBS = [j for j in JOBS if j in want]

RUNS = Path("brands/siftly.ai/runs")
SCORE = Path("brands/siftly.ai/inputs/batch/_shopping_freetools_scorecard.json")
card = json.loads(SCORE.read_text()) if SCORE.exists() else []

def run_ids():
    return {p.name for p in RUNS.iterdir() if p.is_dir()}

def save(card):
    SCORE.write_text(json.dumps(card, indent=2))

print(f"BATCH START: {len(JOBS)} pages, sequential, GOAL enforced", flush=True)
for slug in JOBS:
    # skip if already passed
    prev = next((x for x in card if x["slug"] == slug), None)
    if prev and prev.get("ok"):
        print(f"\n--- SKIP {slug}: already ok (run={prev.get('run')})", flush=True)
        continue
    inp = f"brands/siftly.ai/inputs/batch/{slug}.json"
    print(f"\n=== {slug} ({time.strftime('%H:%M:%S')}) ===", flush=True)
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
    save(card)
print(f"\nBATCH DONE: {sum(1 for x in card if x.get('ok'))}/{len(card)} ok", flush=True)
