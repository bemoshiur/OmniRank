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


def test_graph_children_inherit_container_context():
    payload = {"@context": "https://schema.org",
               "@graph": [{"@type": "Organization", "name": "X"},
                          {"@type": "WebSite", "name": "X"}]}
    assert "seo.schema.no-context" not in ids(jsonld.run(page(payload), URL))


def test_graph_child_keeps_its_own_context():
    payload = {"@context": "https://schema.org",
               "@graph": [{"@context": "https://example.org/ctx",
                           "@type": "Organization", "name": "X"}]}
    blocks = jsonld.extract_blocks(page(payload))
    assert blocks[0]["@context"] == "https://example.org/ctx"


def test_deeply_nested_jsonld_does_not_crash():
    # 200 levels is comfortably above MAX_WALK_DEPTH (100), so this proves the
    # _walk() cap fires, while staying well within what json.dumps/json.loads
    # can encode and parse on Python 3.11's tighter default stack headroom.
    node: dict = {"@type": "Thing"}
    root = node
    for _ in range(200):
        node["nested"] = {"@type": "Thing"}
        node = node["nested"]
    payload = {"@context": "https://schema.org", "@type": "Product", "detail": root}
    findings = jsonld.run(page(payload), URL)   # must not raise
    assert isinstance(findings, list)


def test_pathologically_nested_jsonld_is_reported_not_crashed():
    # Built as a raw string: json.dumps would itself blow the stack here.
    # 200_000 was picked empirically on this machine (CPython 3.14, the C
    # `_json` accelerator): depths up to ~100_000 parsed without incident,
    # while 150_000+ reliably raised RecursionError ("Stack overflow ...
    # while decoding a JSON object"). 200_000 gives comfortable margin above
    # that observed threshold while still parsing/failing in well under a
    # second, so the test stays fast and non-flaky.
    depth = 200_000
    raw = '{"@context":"https://schema.org","@type":"Thing","n":' * depth
    raw += '{"@type":"Thing"}'
    raw += "}" * depth
    html = (f'<html><head><script type="application/ld+json">{raw}</script>'
            f"</head><body></body></html>")
    findings = jsonld.run(html, URL)          # must not raise
    assert "seo.schema.malformed" in {f.id for f in findings}


def test_malformed_block_does_not_hide_other_blocks():
    html = ('<html><head>'
            '<script type="application/ld+json">{not json</script>'
            '<script type="application/ld+json">'
            '{"@context":"https://schema.org","@type":"Review","reviewBody":"x"}'
            '</script></head><body></body></html>')
    found = ids(jsonld.run(html, URL))
    assert "seo.schema.malformed" in found
    assert "seo.schema-fabrication.anonymous-review" in found
