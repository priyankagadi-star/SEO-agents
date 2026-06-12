# SEO/GEO Audit + Content-Generation Agentic Platform

Two LangGraph pipelines sharing one quality spine:

- **Pipeline A — Audit**: live URL (+ optional GSC export) → Master Audit Report + typed `Diagnosis`.
- **Pipeline B — Content**: `rebuild` (from a Diagnosis) or `net_new` (from a seed keyword) → a fully
  packaged page (copy, schema, media manifest, QA checklist) with every fact provenance-tracked.

Quality comes from infrastructure, not prompts: typed state validated at every hand-off, an
append-only Facts Ledger, deterministic guardrails (`fact_diff`, `flag_dont_fill`,
`grounding_check`, `canonical_verify`, `quantifier_check`, `source_precedence`),
writer ≠ verifier separation, and human checkpoints for facts no model can know.

📐 Start here: [`ARCHITECTURE.md`](ARCHITECTURE.md) · contract: [`BUILD-SPEC.md`](BUILD-SPEC.md) · build status: [`CLAUDE.md`](CLAUDE.md)

## Setup

```bash
pip install -r requirements.txt
pytest          # 40+ tests pin the guardrail/ledger/state contracts
```

## The three commands

```bash
# 1. Audit a live URL (Phase 3)
python run.py audit --url https://example.com/page [--gsc export.zip] [--keyword "…"]

# 2. Rebuild a page from its audit diagnosis (Phase 1)
python run.py content --mode rebuild --diagnosis runs/<ts>/diagnosis.json --inputs inputs.json

# 3. Create a new page cold from a keyword (Phase 4)
python run.py content --mode net_new --inputs inputs.json

# GO/KILL gate (Phase 2): rubric ≥85% vs gold AND all 6 seeded poisons caught
python run.py eval
```

Every run writes `runs/<ts>/` with per-node state snapshots, `ledger.json`,
`package_out.json/md`, and a `runlog.md`.

## Multi-domain accounts

Each domain gets its own isolated workspace (config, brand assets, GSC exports, runs) —
adding one is configuration, like adding a property in Google Search Console:

```bash
python run.py account add example.com      # scaffold workspaces/example.com/
# fill in account.yaml + brand_assets.json, drop GSC export ZIPs into gsc/
python run.py audit   --account example.com --url https://example.com/page
python run.py content --account example.com --mode rebuild --diagnosis …
```

Runs land in `workspaces/example.com/runs/<ts>/`. Accounts are fully isolated;
explicit CLI flags always override account config. GSC connects via export files
today; the schema reserves `gsc.mode: api` for a per-domain OAuth upgrade.

## Status

Phase 0 (skeleton & contracts) is complete; Phases 1–5 are tracked in `CLAUDE.md`,
which also lists the owner-supplied reference assets (gold files, prompt kit) that
gate Phase 2.
