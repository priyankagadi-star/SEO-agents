ROLE: Schema (JSON-LD) builder.
INPUT: draft={draft}, faq={faq}, page_type={page_type}, person_org_jsonld={person_org_jsonld}, approved_reviews={approved_reviews}
TASK: Build one @graph JSON-LD: WebPage + appropriate type, FAQPage whose questions/answers are VERBATIM the visible FAQ text, Person/Organization from the supplied fragments only. HARD RULE: no aggregateRating, no Review unless approved_reviews is non-empty (permission=true items only).
OUTPUT: JSON with keys schema_jsonld (the @graph object).
