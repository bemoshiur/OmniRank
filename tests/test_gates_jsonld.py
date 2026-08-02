import json

from omnirank.gates import jsonld

URL = "https://x.example/"


def page(payload) -> str:
    body = json.dumps(payload) if not isinstance(payload, str) else payload
    return (f'<html><head><script type="application/ld+json">{body}</script>'
            f"</head><body></body></html>")


def ids(findings) -> set[str]:
    return {f.id for f in findings}


ORG = {"@context": "https://schema.org", "@type": "Organization",
       "@id": "https://x.example/#organization", "name": "X Example",
       "url": "https://x.example"}


def test_valid_organization_produces_no_findings():
    assert jsonld.run(page(ORG), URL) == []


def test_page_with_no_jsonld_is_an_error():
    found = jsonld.run("<html><head></head><body></body></html>", URL)
    assert found[0].id == "seo.schema.absent"
    assert found[0].gate == "schema"


def test_malformed_json_is_an_error():
    found = [f for f in jsonld.run(page("{not json"), URL) if f.id == "seo.schema.malformed"]
    assert found and found[0].severity == "error"


def test_missing_type_is_an_error():
    assert "seo.schema.no-type" in ids(jsonld.run(page({"@context": "https://schema.org"}), URL))


def test_missing_context_is_a_warning():
    found = [f for f in jsonld.run(page({"@type": "Organization", "name": "X"}), URL)
             if f.id == "seo.schema.no-context"]
    assert found and found[0].severity == "warning"


def test_graph_nodes_are_flattened():
    payload = {"@context": "https://schema.org",
               "@graph": [ORG, {"@type": "WebSite", "name": "X", "url": "https://x.example"}]}
    blocks = jsonld.extract_blocks(page(payload))
    assert {b["@type"] for b in blocks} == {"Organization", "WebSite"}


def test_aggregate_rating_without_count_is_fabrication():
    payload = {"@context": "https://schema.org", "@type": "Product", "name": "X",
               "aggregateRating": {"@type": "AggregateRating", "ratingValue": "5"}}
    found = [f for f in jsonld.run(page(payload), URL)
             if f.id == "seo.schema-fabrication.unbacked-rating"]
    assert found and found[0].severity == "error"
    assert found[0].gate == "schema-fabrication"


def test_aggregate_rating_with_count_passes():
    payload = {"@context": "https://schema.org", "@type": "Product", "name": "X",
               "aggregateRating": {"@type": "AggregateRating", "ratingValue": "4.6",
                                   "ratingCount": 37}}
    assert "seo.schema-fabrication.unbacked-rating" not in ids(jsonld.run(page(payload), URL))


def test_review_without_author_is_fabrication():
    payload = {"@context": "https://schema.org", "@type": "Review",
               "reviewBody": "Great work."}
    assert "seo.schema-fabrication.anonymous-review" in ids(jsonld.run(page(payload), URL))


def test_review_with_author_passes():
    payload = {"@context": "https://schema.org", "@type": "Review",
               "reviewBody": "Great work.",
               "author": {"@type": "Person", "name": "A Real Client"}}
    assert jsonld.run(page(payload), URL) == []
