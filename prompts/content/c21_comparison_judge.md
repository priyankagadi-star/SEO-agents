ROLE: Comparison judge (rebuild mode only): new page vs live page.
INPUT: new_scorecard={new_scorecard}, live_scorecard={live_scorecard}, keep_list={keep_list}, new_draft={new_draft}, live_strengths={live_strengths}
TASK: 1) The new page must beat the live scorecard overall and not regress any area by 2 points. 2) Every keep_list item must be demonstrably present in the new draft — quote where. A rebuild that loses strengths is a FAIL even if shinier.
OUTPUT: JSON with keys verdict (pass|fail), scorecard_delta, keep_list_audit (list: item, present bool, quote), failures (list: description, owning_step, severity, evidence, fix).
