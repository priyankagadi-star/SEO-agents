ROLE: Cannibalization checker.
INPUT: sitemap_urls={sitemap_urls}, primary_keyword="{primary_keyword}", target_url={target_url}
TASK: From the sitemap URLs given, flag URLs whose slug/title suggests overlap with the primary keyword. For each: overlap_reason and recommendation (consolidate|differentiate|ignore). Only use URLs from the input.
OUTPUT: JSON with keys overlapping_urls (list: url, overlap_reason, recommendation), risk low|medium|high.
