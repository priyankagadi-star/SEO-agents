"""c18_schema (L5): JSON-LD @graph built deterministically.

FAQ entities are copied verbatim from the visible FAQ (text == visible text).
NO aggregateRating/Review unless brand_assets carries permission:true reviews.
"""
from __future__ import annotations


def run(state: dict) -> dict:
    target_url = state.get("target_url", "")
    brand = state.get("brand_assets") or {}
    faq = state.get("faq") or []

    graph: list[dict] = [{
        "@type": "WebPage",
        "name": (state.get("brief") or {}).get("title_direction") or state["primary_keyword"],
        "url": target_url,
    }]
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
            "_guardrails": [{"check": "schema", "blocks": len(graph), "approved_reviews": len(approved)}]}
