ROLE: SERP landscape analyst (cold mode).
INPUT: serp_results={serp_results}, primary_keyword="{primary_keyword}"
TASK: From the supplied results only: dominant content format, serp_feature_targets (which features are winnable: PAA, featured snippet, AIO citation), and target word-count range inferred from what ranks. stub=true input => confidence="stub" and no invented competitors.
OUTPUT: JSON with keys dominant_format, serp_feature_targets (list), serp_analysis (notes per result), confidence.
