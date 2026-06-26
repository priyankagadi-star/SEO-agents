#!/usr/bin/env python3
"""Batch page builder. For each manifest entry: run the content pipeline
(advisory GOAL gate so nothing hard-fails), render the page, score it, and
append to a scorecard. Run a subset by passing slugs, else runs all.

Usage: python scripts/run_batch.py [slug ...]
"""
import json
import os
import re
import subprocess
import sys
from pathlib import Path

ROOT = Path(".")
BATCH = Path("brands/siftly.ai/inputs/batch")
manifest = json.loads((BATCH / "_manifest.json").read_text())
want = set(sys.argv[1:])
if want:
    manifest = [m for m in manifest if Path(m["inputs"]).stem in want or m["url"].strip("/").replace("/", "-") in want]

SCORE = BATCH / "_scorecard.json"
scorecard = json.loads(SCORE.read_text()) if SCORE.exists() else []

env = {**os.environ, "GOAL_ENFORCE": "0"}  # advisory: complete + score every page


def latest_runs():
    d = Path("brands/siftly.ai/runs")
    return {p.name for p in d.iterdir() if p.is_dir()} if d.exists() else set()


for m in manifest:
    slug = m["url"].strip("/").replace("/", "-")
    print(f"\n=== {m['url']} ({m['status']}) ===", flush=True)
    before = latest_runs()
    r = subprocess.run([sys.executable, "run.py", "content", "--mode", "net_new",
                        "--account", "siftly.ai", "--inputs", m["inputs"]],
                       capture_output=True, text=True, env=env)
    out = (r.stdout or "") + (r.stderr or "")
    mrun = re.search(r"runs/(\d{8}T\d{6}Z)", out)
    new = sorted(latest_runs() - before)
    run_id = mrun.group(1) if mrun else (new[-1] if new else None)
    if not run_id:
        print("  FAILED — no run dir.", out[-400:], flush=True)
        scorecard.append({"url": m["url"], "status": "ERROR", "log": out[-400:]})
        SCORE.write_text(json.dumps(scorecard, indent=2)); continue
    run_dir = f"brands/siftly.ai/runs/{run_id}"
    # render
    rr = subprocess.run([sys.executable, "scripts/render_page.py", run_dir, m["inputs"]],
                        capture_output=True, text=True)
    # score
    score = None
    try:
        from guardrails import information_gain_score
        from ledger import FactsLedger
        st = json.loads(Path(run_dir, "state.json").read_text())
        brand = json.loads(Path("brands/siftly.ai/brand_assets.json").read_text())
        rd = json.loads(Path(m["inputs"]).read_text())["research_dossier"]
        led = FactsLedger(list(st["facts_ledger"]))
        gr = information_gain_score(st["draft"], led, author=brand.get("author"),
              serp_entities=["generative engine optimization", "answer engine optimization",
                             "ai overviews", "chatgpt", "gemini", "perplexity", "claude",
                             "citation", "llm", "ai visibility"],
              paa_questions=rd.get("real_questions"), faq=st.get("faq"),
              trend_signals=rd.get("trend_signals"), brand_names=["Siftly"],
              owner_domains=["siftly.ai"], word_budget=[1400, 1800], threshold=70)
        score = {"score": gr.score, "passed": gr.passed,
                 "preconditions_ok": all(p["ok"] for p in gr.preconditions.values())}
    except Exception as e:
        score = {"error": str(e)}
    row = {"url": m["url"], "status": m["status"], "run_dir": run_dir,
           "render_ok": rr.returncode == 0, **(score or {})}
    print(f"  -> {run_dir}  score={score}", flush=True)
    scorecard = [s for s in scorecard if s.get("url") != m["url"]] + [row]
    SCORE.write_text(json.dumps(scorecard, indent=2))

print("\n=== SCORECARD ===")
for s in scorecard:
    print(f"  {s['url']:42s} {s.get('score','?')}  passed={s.get('passed','?')}")
