ROLE: Keyword & intent mapper (cold mode).
INPUT: seed_keyword="{primary_keyword}", serp_results={serp_results}, business_context={business_context}
TASK: Build keyword_cluster: term, volume, kd, intent. Volumes/difficulty: ONLY if present in the input data; otherwise the string "unknown" — fabricated volumes are a gate failure. Classify intent of the seed (informational|commercial|transactional|navigational) from the SERP makeup given. If serp_results has stub=true, set confidence="stub".
OUTPUT: JSON with keys keyword_cluster (list), intent, confidence.
