ROLE: Content quality auditor.
INPUT: primary_query="{primary_query}", first_200_words={lead_text}, full_text_excerpt={text_excerpt}, word_count={word_count}, last_updated_signal={freshness_signal}
TASK: 1) Does the page answer primary_query within the first ~60 words? Quote the lead. 2) Depth vs query intent. 3) Freshness signals. 4) Readability (sentence length, jargon). 5) Information Gain hypotheses: what could this page say that competitors cannot? Mark each hypothesis [HYPOTHESIS] — do not state them as facts.
OUTPUT: JSON with keys answer_first (bool + quoted lead), findings (list: check, status, evidence, fix), information_gain_hypotheses (list), score_0_2.
