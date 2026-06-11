ROLE: Brief compiler.
INPUT: strategy={strategy}, unique_insight={unique_insight}, page_type={page_type}, word_budget={word_budget}, ui_limits={ui_limits}, serp_feature_targets={serp_feature_targets}, gap_entity_matrix={gap_entity_matrix}
TASK: Compile the working brief: title_direction (<=60 chars), meta_direction (<=155), structure (ordered section intents), word budget per section summing inside the page budget, media_plan (what visuals where; screenshots are [HUMAN] asks), CTA direction (<=5 words), internal-link targets.
OUTPUT: JSON with keys brief (title_direction, meta_direction, structure, word_budgets, media_plan, cta, internal_link_targets).
