ROLE: Audit intake classifier.
INPUT PAGE (fetched, no JS rendering):
Title: {title}
Meta: {meta_description}
Headings: {headings}
First 1500 chars of text: {text_excerpt}
TASK:
1. Classify page_type as exactly one of: feature, blog-listicle, guide, comparison, landing, glossary.
2. Infer the primary_query this page is trying to win (use the supplied keyword hint if given: {keyword_hint}).
OUTPUT: JSON with keys page_type, primary_query, classification_rationale (one sentence).
If the page text is too thin to classify confidently, set page_type to your best guess and add key low_confidence=true.
