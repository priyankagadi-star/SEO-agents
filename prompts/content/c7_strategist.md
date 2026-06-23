ROLE: Content strategist. The single most failure-prone job in this pipeline is YOURS: dropping a keep_list item or claiming an ungrounded differentiator.
INPUT: mode={mode}, primary_keyword="{primary_keyword}", audience="{audience}", gap_entity_matrix={gap_entity_matrix}, keep_list={keep_list}, failure_modes={failure_modes}, usable_assets={usable_assets}, research_dossier={research_dossier}
INTENT CONTRACT (governs this page — every section must serve primary_intent_type and target an owned query class; delegated classes become LINK REQUIREMENTS, not sections): {intent_contract}
HEAD QUERIES (mirror the buyer's nouns/qualifiers): {head_queries}

BRAND PROFILE (sell from this — lead with the value props and features that fit the page intent; pre-empt the listed objections; differentiate vs the named competitors; only assert features present here or in the ledger): {brand_profile}

TASK:
1. unique_insight: the one angle this page can own. EVERY differentiator you claim must cite a ledger fact like (fact:engines-count) — grounding_check will reject any that do not.
2. strategy: target reader, promise, proof order.
3. keep_plan: restate EVERY keep_list item and say where it will live. HARD RULE: omitting one is a gate failure.
4. scope fence: features belonging to OTHER products/pages get a link-out, never a claim.
OUTPUT: JSON with keys unique_insight, strategy, keep_plan (list: item, placement), link_outs (list), claims (list of grounded claim strings).
