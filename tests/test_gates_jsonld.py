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



# --- v0.2.1: MIME type tokens are case-insensitive, and a ;charset parameter is
# not part of the type -- neither may cause a real JSON-LD block to be reported as
# absent. Each pair below reproduces one confirmed false positive, then a companion
# proving a genuinely non-JSON-LD script (same case quirk, wrong type) is still
# correctly reported absent. ---

def test_uppercase_ldjson_type_is_not_flagged_absent():
    html = (f'<html><head><script type="application/LD+JSON">{json.dumps(ORG)}'
            f"</script></head><body></body></html>")
    assert "seo.schema.absent" not in ids(jsonld.run(html, URL))


def test_non_ldjson_type_regardless_of_case_is_still_flagged_absent():
    html = (f'<html><head><script type="application/JSON">{json.dumps(ORG)}'
            f"</script></head><body></body></html>")
    found = jsonld.run(html, URL)
    assert found[0].id == "seo.schema.absent"


def test_ldjson_type_with_charset_parameter_is_not_flagged_absent():
    html = (f'<html><head><script type="application/ld+json; charset=utf-8">'
            f"{json.dumps(ORG)}</script></head><body></body></html>")
    assert "seo.schema.absent" not in ids(jsonld.run(html, URL))


def test_non_ldjson_type_with_charset_parameter_is_still_flagged_absent():
    html = (f'<html><head><script type="application/json; charset=utf-8">'
            f"{json.dumps(ORG)}</script></head><body></body></html>")
    found = jsonld.run(html, URL)
    assert found[0].id == "seo.schema.absent"


def test_malformed_block_does_not_hide_other_blocks():
    html = ('<html><head>'
            '<script type="application/ld+json">{not json</script>'
            '<script type="application/ld+json">'
            '{"@context":"https://schema.org","@type":"Review","reviewBody":"x"}'
            '</script></head><body></body></html>')
    found = ids(jsonld.run(html, URL))
    assert "seo.schema.malformed" in found
    assert "seo.schema-fabrication.anonymous-review" in found


from omnirank.gates.jsonld import RICH_RESULT_RULES, RICH_RESULT_RULES_AS_OF


def ld(payload: str) -> str:
    return (f'<html><head><script type="application/ld+json">{payload}</script>'
            "</head><body></body></html>")


def required_findings(html: str) -> list:
    return [f for f in jsonld.run(html, "https://x.example/")
            if f.id == "seo.schema-required.missing-property"]


def test_an_article_without_date_published_is_flagged():
    html = ld('{"@context":"https://schema.org","@type":"Article",'
              '"headline":"H","image":"https://x.example/i.png"}')
    found = required_findings(html)
    assert len(found) == 1
    assert found[0].severity == "warning"
    assert found[0].layer == "seo"
    assert found[0].gate == "schema-required"
    assert "Article" in found[0].observed
    assert "datePublished" in found[0].observed


def test_a_complete_article_is_not_flagged():
    html = ld('{"@context":"https://schema.org","@type":"Article","headline":"H",'
              '"image":"https://x.example/i.png","datePublished":"2026-01-01"}')
    assert required_findings(html) == []


def test_blogposting_and_newsarticle_share_the_article_rules():
    for type_name in ("BlogPosting", "NewsArticle"):
        html = ld(f'{{"@context":"https://schema.org","@type":"{type_name}",'
                  '"headline":"H"}')
        found = required_findings(html)
        assert len(found) == 1, type_name
        assert "image" in found[0].observed and "datePublished" in found[0].observed


def test_one_finding_per_node_listing_every_missing_property():
    html = ld('{"@context":"https://schema.org","@type":"Article"}')
    found = required_findings(html)
    assert len(found) == 1, "one finding per node, not one per property"
    for prop in ("headline", "image", "datePublished"):
        assert prop in found[0].observed, prop


def test_product_accepts_any_one_of_offers_rating_or_review():
    for alternative in ("offers", "aggregateRating", "review"):
        html = ld('{"@context":"https://schema.org","@type":"Product","name":"P",'
                  f'"{alternative}":{{"@type":"Thing"}}}}')
        assert required_findings(html) == [], alternative


def test_a_product_with_none_of_the_three_alternatives_is_flagged():
    html = ld('{"@context":"https://schema.org","@type":"Product","name":"P"}')
    found = required_findings(html)
    assert len(found) == 1
    for alternative in ("offers", "aggregateRating", "review"):
        assert alternative in found[0].observed, alternative


def test_a_faqpage_whose_questions_have_no_accepted_answer_is_flagged():
    html = ld('{"@context":"https://schema.org","@type":"FAQPage","mainEntity":'
              '[{"@type":"Question","name":"Q?"}]}')
    found = required_findings(html)
    assert len(found) == 1
    assert "acceptedAnswer" in found[0].observed


def test_a_faqpage_with_an_accepted_answer_passes():
    html = ld('{"@context":"https://schema.org","@type":"FAQPage","mainEntity":'
              '[{"@type":"Question","name":"Q?","acceptedAnswer":'
              '{"@type":"Answer","text":"A"}}]}')
    assert required_findings(html) == []


def test_a_breadcrumb_item_missing_position_is_flagged():
    html = ld('{"@context":"https://schema.org","@type":"BreadcrumbList",'
              '"itemListElement":[{"@type":"ListItem","name":"Home"}]}')
    found = required_findings(html)
    assert len(found) == 1
    assert "position" in found[0].observed


def test_a_breadcrumb_name_nested_under_item_is_accepted():
    # Google documents BOTH shapes. Flagging the nested one would be a fabricated
    # error on entirely valid markup.
    html = ld('{"@context":"https://schema.org","@type":"BreadcrumbList",'
              '"itemListElement":[{"@type":"ListItem","position":1,'
              '"item":{"@id":"https://x.example/","name":"Home"}}]}')
    assert required_findings(html) == []


def test_organization_needs_name_and_url():
    html = ld('{"@context":"https://schema.org","@type":"Organization","name":"X"}')
    found = required_findings(html)
    assert len(found) == 1 and "url" in found[0].observed


def test_localbusiness_needs_name_and_address():
    html = ld('{"@context":"https://schema.org","@type":"LocalBusiness","name":"X"}')
    found = required_findings(html)
    assert len(found) == 1 and "address" in found[0].observed


def test_an_untyped_or_unknown_type_is_left_alone():
    html = ld('{"@context":"https://schema.org","@type":"WebPage","name":"X"}')
    assert required_findings(html) == [], (
        "OmniRank has no rich-result rule for WebPage and must not invent one")


def test_a_pure_id_reference_stub_is_not_flagged():
    # A node that is only @type + @id is a REFERENCE to an entity declared
    # elsewhere, not a declaration missing its properties.
    html = ld('{"@context":"https://schema.org","@graph":['
              '{"@type":"Organization","@id":"https://x.example/#org"},'
              '{"@type":"WebPage","@id":"https://x.example/#page"}]}')
    assert required_findings(html) == []


def test_a_whitespace_only_value_does_not_count_as_present():
    html = ld('{"@context":"https://schema.org","@type":"Organization",'
              '"name":"   ","url":"https://x.example/"}')
    found = required_findings(html)
    assert len(found) == 1 and "name" in found[0].observed


def test_an_empty_list_value_does_not_count_as_present():
    html = ld('{"@context":"https://schema.org","@type":"FAQPage","mainEntity":[]}')
    found = required_findings(html)
    assert len(found) == 1 and "mainEntity" in found[0].observed


def test_a_multi_typed_node_is_checked_against_every_rule_it_declares():
    html = ld('{"@context":"https://schema.org",'
              '"@type":["Organization","LocalBusiness"],"name":"X"}')
    found = required_findings(html)
    assert len(found) == 1
    assert "url" in found[0].observed and "address" in found[0].observed


def test_the_finding_distinguishes_schema_org_validity_from_google_eligibility():
    html = ld('{"@context":"https://schema.org","@type":"Article"}')
    fix = required_findings(html)[0].fix
    assert "schema.org" in fix, "the text must name whose requirement is unmet"
    assert "Google" in fix
    assert RICH_RESULT_RULES_AS_OF in fix, (
        "the table's transcription date must be inspectable from the finding")
    assert "RICH_RESULT_RULES" in fix


def test_every_documented_type_has_at_least_one_requirement_group():
    assert set(RICH_RESULT_RULES) >= {
        "Article", "BlogPosting", "NewsArticle", "Product", "FAQPage",
        "BreadcrumbList", "Organization", "LocalBusiness"}
    for type_name, groups in RICH_RESULT_RULES.items():
        assert groups, type_name
        for group in groups:
            assert group and all(isinstance(p, str) for p in group), type_name
