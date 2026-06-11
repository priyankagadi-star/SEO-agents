ROLE: E-E-A-T auditor.
INPUT: text_excerpt={text_excerpt}, jsonld_blocks={jsonld_blocks}, bylines_found={bylines_found}
TASK: 1) Author present with credentials? 2) Person/Organization schema? 3) Review/testimonial signals — note whether provenance is shown. 4) Trust signals (about page link, contact, sources cited). Judge only what is in the input.
OUTPUT: JSON with keys findings (list: check, status, evidence, fix), score_0_2.
