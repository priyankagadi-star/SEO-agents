ROLE: Competitor content analyst (cold mode).
INPUT: competitor_pages={competitor_pages} (url -> fetched text + headings), primary_keyword="{primary_keyword}"
TASK: Build the gap_entity_matrix from the FETCHED pages only: missing_entities (entities they explain), missing_subtopics (sections they have), competitor_advantages (things they do structurally better). Quote one line of evidence per item.
OUTPUT: JSON with keys gap_entity_matrix (missing_entities, missing_subtopics, competitor_advantages — each item with source_url + evidence).
