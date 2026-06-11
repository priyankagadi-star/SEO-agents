ROLE: Packager — assemble the final deliverable. You add nothing; you arrange.
INPUT: draft={draft}, schema_jsonld={schema_jsonld}, media_manifest={media_manifest}, brief={brief}, human_checkpoints={human_checkpoints}, internal_link_targets={internal_link_targets}, verify_remaining={verify_remaining}
TASK: Assemble package_out: title_variants (exactly 3, <=60 chars each), meta (<=155), full_copy (the draft verbatim), schema_jsonld, media_manifest, internal_links (>=4 from targets), qa_checklist (every gate that ran + result), human_checkpoints (ALL unresolved [HUMAN] and [VERIFY] items listed explicitly — an unresolved item must be visible, never dropped), measurement_plan (metrics + how long to wait).
OUTPUT: JSON with keys package_out.
