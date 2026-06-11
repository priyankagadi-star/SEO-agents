# eval/gold — MISSING, owner must supply [VERIFY-WITH-OWNER]

BUILD-SPEC §9 requires these four gold files, which were **not present in the
repository**. The Phase 2 GO/KILL gate cannot run until they are copied here:

1. `siftly-ai-brand-monitoring.html`
2. `siftly-chatgpt-visibility.html`
3. `chatgpt-visibility-content-package.md` (from `page-runs/`)
4. `RUNLOG-chatgpt-visibility.md` (from `page-runs/`)

Also needed for Phase 1: `page-runs/02-chatgpt-visibility.md` (source for the
hand-written `diagnosis.json`).

Do not fabricate stand-ins for these — the eval gate is only meaningful against
the real gold run.
