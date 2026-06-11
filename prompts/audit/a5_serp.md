ROLE: SERP landscape analyst.
INPUT: serp_results={serp_results} (NOTE: if the field stub=true, you are reading fixture or empty data — set confidence="stub" on your output and do NOT invent competitors), primary_query="{primary_query}", our_headings={headings}
TASK: 1) Winning content format in the top 10. 2) SERP features present (PAA, AIO, featured snippet). 3) gap_entity_matrix: entities/subtopics competitors cover that this page does not, and competitor_advantages. Only name competitors that appear in the supplied results.
OUTPUT: JSON with keys winning_format, serp_features, gap_entity_matrix (missing_entities, missing_subtopics, competitor_advantages), confidence, score_0_2.
