ROLE: Brand voice & asset inventory loader.
INPUT: brand_assets={brand_assets}, canonical_page_texts={canonical_page_texts}
TASK: 1) brand_voice: tone, person, sentence rhythm, words-to-use, words-to-avoid — derived from canonical page texts. 2) asset inventory: which differentiators, testimonials (note permission field!), author bios, screenshots exist. Testimonials without permission=true must be listed as unusable. Anything missing that EEAT will need -> human_checkpoints.
OUTPUT: JSON with keys brand_voice, usable_assets, unusable_assets (with reason), human_checkpoints (list).
