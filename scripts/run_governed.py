"""Run pages GSC-governed: each page fed its own per-page GSC export via --gsc,
GOAL gate enforced. Writes a governed scorecard. Usage: python scripts/run_governed.py [slug...]"""
import json, os, re, subprocess, sys
from pathlib import Path
sys.path.insert(0, str(Path.cwd()))

U = "/root/.claude/uploads/5a0795d6-5e51-55c1-85bb-47f0134a6eb0"
JOBS = [
    ("features-chatgpt-visibility", f"{U}/121a872b-siftly.aiPerformanceonSearch20260627_3.zip"),
    ("blog-track-brand-mentions",   f"{U}/3e660a38-siftly.aiPerformanceonSearch20260627_1.zip"),
    ("blog-citation-rates",         f"{U}/2698a8eb-siftly.aiPerformanceonSearch20260627_2.zip"),
    ("blog-brand-monitoring",       f"{U}/719cea3d-siftly.aiPerformanceonSearch20260627.zip"),
]
want = set(sys.argv[1:])
if want:
    JOBS = [j for j in JOBS if j[0] in want]

RUNS = Path("brands/siftly.ai/runs")
SCORE = Path("brands/siftly.ai/inputs/batch/_governed_scorecard.json")
card = json.loads(SCORE.read_text()) if SCORE.exists() else []

def run_ids():
    return {p.name for p in RUNS.iterdir() if p.is_dir()}

for slug, gsc in JOBS:
    inp = f"brands/siftly.ai/inputs/batch/{slug}.json"
    print(f"\n=== {slug} (governed --gsc {Path(gsc).name}) ===", flush=True)
    before = run_ids()
    env = {**os.environ, "GOAL_ENFORCE": "1"}
    r = subprocess.run([sys.executable, "run.py", "content", "--mode", "net_new",
                        "--account", "siftly.ai", "--inputs", inp, "--gsc", gsc],
                       capture_output=True, text=True, env=env)
    out = (r.stdout or "") + (r.stderr or "")
    m = re.search(r"runs/(\d{8}T\d{6}Z)", out)
    new = sorted(run_ids() - before)
    rid = m.group(1) if m else (new[-1] if new else None)
    g = re.search(r"loaded (\d+) GSC queries", out)
    c = re.search(r"input contract ok — (\w+) page", out)
    ok = bool(rid) and Path(RUNS, rid, "package_out.json").exists() if rid else False
    rec = {"slug": slug, "run": rid, "gsc_queries": int(g.group(1)) if g else 0,
           "contract": c.group(1) if c else "?", "ok": ok}
    if not ok:
        rec["tail"] = out[-400:]
    print(f"  -> run={rid} gsc_q={rec['gsc_queries']} contract={rec['contract']} ok={ok}", flush=True)
    card = [x for x in card if x["slug"] != slug] + [rec]
    SCORE.write_text(json.dumps(card, indent=2))
print("\nGOVERNED BATCH DONE", flush=True)
