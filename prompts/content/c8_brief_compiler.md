ROLE: Brief compiler.
INPUT: strategy={strategy}, unique_insight={unique_insight}, page_type={page_type}, word_budget={word_budget}, ui_limits={ui_limits}, serp_feature_targets={serp_feature_targets}, gap_entity_matrix={gap_entity_matrix}
CANDIDATE ADDITIONS (subtopics competitors cover and trend signals — add to the structure ONLY when they meaningfully serve THIS page's intent or beat the current competitive shape; do NOT add filler. Required blocks stay; additions extend): {candidate_additions}
TREND SIGNALS (current landscape — surface as 'Why now' / 'What's changed' style sections when relevant): {trend_signals}
MARKET STATS (real, sourced search-demand/market data — already seeded as ledger facts; build a 'Why this matters now' market-context section that cites them): {market_stats}
EXTERNAL SOURCES (authoritative third-party references already seeded as ledger facts; have the writer corroborate claims against these for E-E-A-T trust): {external_sources}
REAL QUESTIONS (actual searcher PAA — ensure the FAQ/section coverage answers these): {real_questions}

REQUIRED STRUCTURE for this page_type (every block MUST appear in your structure; you may add more, never drop these): {required_blocks}
SCHEMA TYPES this page_type should emit: {schema_types}

TASK: Compile the working brief: title_direction (<=60 chars), meta_direction (<=155), structure (ordered section intents), word budget per section summing inside the page budget, media_plan (what visuals where; screenshots are [HUMAN] asks), CTA direction (<=5 words), internal-link targets.
OUTPUT: JSON with keys brief (title_direction, meta_direction, structure, word_budgets, media_plan, cta, internal_link_targets).
