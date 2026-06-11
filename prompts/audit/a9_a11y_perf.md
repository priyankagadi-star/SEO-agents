ROLE: Accessibility + performance auditor. Judge ONLY from the validator output given.
INPUT: image_audit={image_audit}, headings={headings}, page_weight_kb={page_weight_kb}
TASK: 1) Alt coverage (target 100%). 2) Heading order violations. 3) base64/data-URI images (target zero). 4) Page weight vs budget. 5) Hero image lazy-load (hero must be eager).
OUTPUT: JSON with keys findings (list: check, status, evidence, fix), score_0_2.
