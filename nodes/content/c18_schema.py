"""c18_schema (L5): JSON-LD @graph built deterministically.

FAQ entities are copied verbatim from the visible FAQ (text == visible text).
NO aggregateRating/Review unless brand_assets carries permission:true reviews.
"""
from __future__ import annotations

from page_profiles import get_profile


def run(state: dict) -> dict:
    target_url = state.get("target_url", "")
    brand = state.get("brand_assets") or {}
    faq = state.get("faq") or []
    profile = get_profile(state.get("page_type"))
    schema_types = (state.get("brief") or {}).get("schema_types") or list(profile.schema_types)
    name = (state.get("brief") or {}).get("title_direction") or state["primary_keyword"]

    graph: list[dict] = [{"@type": "WebPage", "name": name, "url": target_url}]

    # page-type-specific primary entity
    if "SoftwareApplication" in schema_types:
        graph.append({"@type": "SoftwareApplication", "name": name,
                      "applicationCategory": "BusinessApplication"})
    if "DefinedTerm" in schema_types:
        definition = (state.get("lead") or "").strip()
        graph.append({"@type": "DefinedTerm", "name": state["primary_keyword"],
                      "description": definition})
    if "HowTo" in schema_types:
        steps = [{"@type": "HowToStep", "name": s.get("h2", "")}
                 for s in (state.get("outline") or {}).get("sections", []) if s.get("h2")]
        if steps:
            graph.append({"@type": "HowTo", "name": name, "step": steps})
    if "ItemList" in schema_types:
        items = [{"@type": "ListItem", "position": i + 1, "name": s.get("h2", "")}
                 for i, s in enumerate((state.get("outline") or {}).get("sections", [])) if s.get("h2")]
        if items:
            graph.append({"@type": "ItemList", "itemListElement": items})

    if faq:
        graph.append({
            "@type": "FAQPage",
            "mainEntity": [
                {"@type": "Question", "name": f.get("q", ""),
                 "acceptedAnswer": {"@type": "Answer", "text": f.get("a", "")}}
                for f in faq
            ],
        })
    author = brand.get("author")
    if isinstance(author, dict) and author.get("name"):
        person = {"@type": "Person", "name": author["name"]}
        if author.get("credentials"):
            person["description"] = author["credentials"]
        graph.append(person)

    approved = [t for t in brand.get("testimonials", []) if isinstance(t, dict) and t.get("permission")]
    # invariant: Review/aggregateRating only from approved reviews
    for t in approved:
        graph.append({
            "@type": "Review",
            "reviewBody": t.get("quote", ""),
            "author": {"@type": "Person", "name": t.get("author", "Anonymous")},
        })

    schema = {"@context": "https://schema.org", "@graph": graph}
    return {"schema_jsonld": schema,
            "_guardrails": [{"check": "schema", "page_type": profile.page_type,
                             "types": [b.get("@type") for b in graph],
                             "approved_reviews": len(approved)}]}
