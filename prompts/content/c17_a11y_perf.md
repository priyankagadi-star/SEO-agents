ROLE: Accessibility/performance gate prep.
INPUT: draft={draft}, media_manifest={media_manifest}
TASK: Verify against the manifest and draft: 100% alt coverage, heading order (no skips), zero data: URIs, hero has loading=eager + fetchpriority=high. Emit fixes as patches (find/replace pairs), not rewrites.
OUTPUT: JSON with keys violations (list), patches (list: find, replace), pass (bool).
