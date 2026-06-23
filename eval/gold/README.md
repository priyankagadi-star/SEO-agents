# eval/gold — optional quality references (owner QA)

The eval gate has two halves (see `eval/run_eval.py`):

1. **Safety suite — runs without anything here.** The 6 seeded poisons run against
   the real guardrails (`python run.py eval`). This is the hard GO/KILL gate.

2. **Quality rubric — optional, grades against a gold pair you drop in here.**
   Gold is the owner's QA reference for *specific pages you choose to test* — it is
   NOT a structural dependency, and its absence does not block the gate.

To score quality vs a known-good page, drop two `package_out`-shaped JSON files:

```
eval/gold/<name>.gold.json        # the known-good package (your hand-made reference)
eval/gold/<name>.candidate.json   # a package the platform produced for the same page
```

Each is the `package_out.json` shape a run already writes (optionally with a
`"_state"` key carrying the run state for entity/fact checks). The rubric then
reports candidate score vs gold and PASS/FAIL at `rubric_pass_pct` (config.yaml).

The original Siftly samples (`siftly-*.html`, `chatgpt-visibility-content-package.md`,
`RUNLOG-chatgpt-visibility.md`) were one owner test set — useful but not required.
Convert any to a `*.gold.json` package to grade against it.
