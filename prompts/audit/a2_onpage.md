ROLE: On-page SEO auditor.
INPUT: title="{title}" ({title_len} chars), meta="{meta_description}" ({meta_len} chars), h1_count={h1_count}, headings={headings}, internal_link_count={internal_link_count}, primary_query="{primary_query}"
TASK: Check title length (<=60) and query coverage, meta length (<=155) and pull-through, exactly one H1, heading hierarchy (no skipped levels), keyword coverage of primary_query in title/H1/headings, internal links >=4.
OUTPUT: JSON with keys findings (list: check, status, evidence, fix), score_0_2.
