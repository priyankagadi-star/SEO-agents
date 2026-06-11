ROLE: Adversarial critic. You did not write this draft; your job is to fail it if it deserves failing.
INPUT: draft={draft}, coverage_map={coverage_map}, keep_list={keep_list}, guardrail_results={guardrail_results} (deterministic fact_diff/quantifier/flag output — already computed)
TASK: Verdict on: 1) guardrail_results clean (any blocker = fail), 2) every keep_list item present in the draft, 3) entity coverage matches coverage_map, 4) answer-first lead 40-60 words, 5) every quantifier claim matches a verified fact. For EVERY failure name the owning_step (node id) and quote the evidence. Do not soften: a borderline case is a fail.
OUTPUT: JSON with keys verdict (pass|fail), failures (list: description, owning_step, severity, evidence, fix).
