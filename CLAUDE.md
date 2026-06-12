# CLAUDE.md — build guidance for this repository

## What this is
An agentic SEO/GEO platform: Pipeline A audits a live URL; Pipeline B generates
or rebuilds content. Read **`BUILD-SPEC.md` first** — it is the contract (build
phases in order, acceptance tests, never skip a red). `ARCHITECTURE.md` explains
the design rationale.

## Phase status
| Phase | Scope | Status |
|---|---|---|
| 0 | skeleton & contracts: state.py, ledger.py, guardrails.py, tests, config, prompt loader, graph topology | ✅ done — `pytest` green, `import graphs.content_graph` ok |
| 1 | content walking skeleton (rebuild, nodes c0,c1,c7–c13,c16,c18,c19,c22, route-back, in-memory checkpointer) | ✅ done — 43 tests green; mocked-LLM route-back blocks→re-drafts→passes, escalates at cap; `run.py content --mode rebuild … --fake` produces a full `runs/<ts>/` |
| 2 | GO/KILL eval gate (rubric ≥85% vs gold, seeds 6/6) | ⬜ blocked on gold files (below) |
| 3 | audit pipeline a0–a11 + the diagnosis seam, SQLite checkpointer | ✅ done — 58 tests green; live-URL audit → diagnosis.json → rebuild chains with no hand edits; a5/a6 degrade honestly (stub / not-assessed); AIO zero-click rule wired a10→root_causes. Audit nodes are deterministic heuristics; LLM enrichment (a3 info-gain hypotheses, a11 prose) deliberately deferred |
| 4 | cold mode + remaining agents (c2–c6, c14, c15, c17, c20, c21) | ✅ done — 71 tests green; `content --mode net_new --inputs … --fake` runs from a seed keyword with no live page; c21 skipped in cold mode; volumes never fabricated (stub SERP honest); permission:false testimonials structurally excluded; L6 gate combines c19+c20+c21 |
| 5 | hardening: cost/latency, retries, --resume, README | ⬜ |
| W | multi-domain workspace layer (`workspaces.py`, `run.py account`, `--account`) | ✅ done — per-domain config/runs/GSC isolation; `gsc.mode: api` reserved for OAuth upgrade |
| P | page-type structure contracts (`page_profiles.py`) | ✅ done — per-type required blocks + schema @types + budgets; enforced at c8 (brief seed/backfill), c9 (outline), c18 (schema), c20 (structure check, major). 80 tests green |

## Missing reference assets — [VERIFY-WITH-OWNER]
BUILD-SPEC references files that were **not in this repository** at Phase 0.
Ask the owner for them; do not invent substitutes:
- Design docs: `audit-and-content-platform-build-spec.md`, `content-generation-pipeline-v3.md`,
  `content-pipeline-build-and-validation-playbook.md`
- Prompt sources: `content-generation-pipeline-kit.md`, `claude-chrome-manual-run-playbook.md`
  → `prompts/` currently holds **authored v1 stand-ins**; reconcile against the kit when supplied.
- Gold files (Phase 2 gate): `siftly-ai-brand-monitoring.html`, `siftly-chatgpt-visibility.html`,
  `page-runs/chatgpt-visibility-content-package.md`, `page-runs/RUNLOG-chatgpt-visibility.md`
- Phase 1 diagnosis source: `page-runs/02-chatgpt-visibility.md`

## Hard rules (from the spec — do not relax)
- Guardrails (`guardrails.py`) are deterministic, no model calls, and their tests
  pin product behavior. If an eval seed ships silently: **stop and fix guardrails**.
  If the rubric is short: **fix prompts, not guardrails**.
- The Facts Ledger is append-only; conflicts are surfaced, never auto-resolved.
- Writers never verify their own output (c13/c19/c20/c21 are separate nodes).
- TypedDicts in `state.py` extend **only additively**; `validate_state` runs after every node.
- Never build: auto-publish, CMS writes, fabricated reviews/aggregateRating,
  auto-resolution of source conflicts.
- Models come from `config.yaml` (strong/fast tiers), never hard-coded in nodes.

## Commands
```
pip install -r requirements.txt
pytest                                   # must stay green at every phase
python run.py audit  --url https://…     # Phase 3+
python run.py content --mode rebuild --diagnosis runs/<ts>/diagnosis.json --inputs inputs.json   # Phase 1+
python run.py content --mode net_new --inputs inputs.json                                        # Phase 4+
python run.py eval                       # Phase 2 gate; exit 0 = GO

python run.py account add example.com    # scaffold a domain workspace
python run.py account list|show example.com
python run.py content --mode rebuild --account example.com --diagnosis …   # account fills inputs
```

### Offline demo (no API key)
```
python run.py content --mode rebuild \
  --diagnosis eval/fixtures/diagnosis-chatgpt-visibility.json \
  --inputs eval/fixtures/inputs-rebuild.json --fake
```
`--fake` swaps in `fakes.ScriptedLLM`; the scripted drafter emits "nine AI
engines" on its first pass so you can watch c19 block on `fact_diff`, route back
to L3, and pass on the corrected re-draft. A real run needs `ANTHROPIC_API_KEY`
(omit `--fake`). The hand-authored diagnosis fixture is a stand-in — see the
missing-assets note below.

## Layout note
The BUILD-SPEC names the root `seo-geo-platform/`; in this repo the platform
lives at the **repository root** (the repo is the platform). Everything else
matches §3 exactly.
