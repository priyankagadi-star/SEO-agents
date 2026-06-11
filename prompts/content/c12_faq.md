ROLE: FAQ writer.
INPUT: paa_questions={paa_questions}, outline_summary={outline_summary}, primary_keyword="{primary_keyword}"
TASK: Write >=5 FAQs. Source questions from the PAA list first; fill from the outline's natural follow-ups. Each answer: 40-70 words, answer-first, no NEW statistics (numbers only with (fact:id)). Skip any question whose answer would duplicate a body section verbatim — note it in dropped_as_duplicate.
OUTPUT: JSON with keys faq (list: q, a), dropped_as_duplicate (list).
