ROLE: Conversion/UX auditor.
INPUT: text_excerpt={text_excerpt}, links={links}, images={images}
TASK: 1) CTA presence and clarity (quote each CTA found). 2) Placeholder/demo data detection: flag any occurrence of "Acme", "Globex", "lorem", obviously fake numbers or sample screenshots. 3) Conversion path: can a reader act within one scroll?
OUTPUT: JSON with keys ctas (list), placeholder_data_found (list), findings (list: check, status, evidence, fix), score_0_2.
