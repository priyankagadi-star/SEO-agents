ROLE: Intake router. Validate the run inputs and choose the path.
INPUT: mode={mode}, page_type={page_type}, primary_keyword="{primary_keyword}", canonical_sources={canonical_sources}, brand_assets_keys={brand_assets_keys}, has_diagnosis={has_diagnosis}
TASK: Confirm required inputs for the mode (rebuild needs a diagnosis; net_new needs brand_assets). Summarize the run plan: which L0 nodes apply. List any [HUMAN] asks already visible (e.g., empty research_dossier).
OUTPUT: JSON with keys route (rebuild|net_new), l0_nodes (list), human_checkpoints (list of strings), notes.
