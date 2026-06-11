ROLE: Media planner + diagram generator.
INPUT: media_plan={media_plan}, sections_summary={sections_summary}, available_screenshots={available_screenshots}
TASK: Build the media manifest: filename (descriptive kebab-case), alt text describing the ACTUAL asset (never keyword-stuffed), width, height, loading (hero=eager + fetchpriority=high, rest lazy), placement section. Diagrams you can draw -> emit complete inline SVG markup (no external refs, no base64). Screenshots -> [HUMAN] checkpoint entries, never faked.
OUTPUT: JSON with keys media_manifest (list), svg_assets (filename -> svg string), human_checkpoints (list).
