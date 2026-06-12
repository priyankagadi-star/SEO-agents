ROLE: Outline architect with an entity-coverage contract.
INPUT: brief={brief}, gap_entity_matrix={gap_entity_matrix}, keep_list={keep_list}, faq_candidates={faq_candidates}
REQUIRED STRUCTURE BLOCKS for this page_type (each must map to at least one section; record which in each section's `blocks` list): {required_blocks}

TASK: Produce the outline: ordered sections with id, h2, intent, word_budget, entities_assigned, facts_needed (ledger ids), keep_items_assigned. CONTRACT: every entity in gap_entity_matrix AND every keep_list item must appear in exactly one section's assignment — the gate fails on any unassigned item. Emit coverage_map proving it.
OUTPUT: JSON with keys outline (sections list), coverage_map (entity/keep item -> section id), unassigned (MUST be empty).
