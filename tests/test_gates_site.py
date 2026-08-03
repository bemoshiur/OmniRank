from omnirank.gates import site
from omnirank.page import PageData

SITE = "https://x.example"


def page(path: str, title: str = "Unique Title", description: str = "Unique.",
         extra_head: str = "", body: str = "<h1>H</h1>", lang: str = "en") -> PageData:
    html = (f"<!doctype html><html lang='{lang}'><head>"
            f"<title>{title}</title>"
            f'<meta name="description" content="{description}">'
            f"{extra_head}</head><body>{body}</body></html>")
    return PageData(url=f"{SITE}{path}", html=html, status=200,
                    elapsed_ms=10, headers={})


def ids(findings) -> set[str]:
    return {f.id for f in findings}


def test_unique_titles_produce_no_finding():
    pages = [page("/a", title="Alpha"), page("/b", title="Beta")]
    assert "seo.duplicate-title.shared" not in ids(site.run(pages))


def test_duplicate_titles_are_flagged_once_for_the_group():
    pages = [page("/a", title="Same"), page("/b", title="Same"), page("/c", title="Same")]
    found = [f for f in site.run(pages) if f.id == "seo.duplicate-title.shared"]
    assert len(found) == 1, "one finding per group, not per affected URL"
    assert found[0].severity == "warning"
    assert found[0].gate == "duplicate-title"
    assert "3" in found[0].observed
    assert f"{SITE}/b" in found[0].fix or f"{SITE}/b" in found[0].observed


def test_title_comparison_ignores_case_and_surrounding_whitespace():
    pages = [page("/a", title="Same Title"), page("/b", title="  same title  ")]
    assert "seo.duplicate-title.shared" in ids(site.run(pages))


def test_duplicate_descriptions_are_flagged():
    pages = [page("/a", description="Shared copy."),
             page("/b", description="Shared copy.")]
    found = [f for f in site.run(pages) if f.id == "seo.duplicate-description.shared"]
    assert found and found[0].gate == "duplicate-description"


def test_empty_titles_are_not_treated_as_duplicates():
    pages = [page("/a", title=""), page("/b", title="")]
    assert "seo.duplicate-title.shared" not in ids(site.run(pages)), (
        "a missing title is the per-URL gate's job, not a duplicate")


def test_a_single_page_can_never_duplicate():
    assert site.run([page("/a")]) == []


def test_no_pages_is_not_an_error():
    assert site.run([]) == []


NOINDEX = '<meta name="robots" content="noindex, follow">'
GOOGLEBOT_NOINDEX = '<meta name="googlebot" content="NOINDEX">'
INDEX_OK = '<meta name="robots" content="index, follow">'


def test_noindex_page_in_sitemap_is_an_error():
    pages = [page("/a", extra_head=NOINDEX)]
    found = [f for f in site.run(pages, [f"{SITE}/a"])
             if f.id == "seo.noindex.in-sitemap"]
    assert found and found[0].severity == "error"
    assert found[0].gate == "noindex-in-sitemap"


def test_noindex_page_absent_from_sitemap_is_fine():
    pages = [page("/a", extra_head=NOINDEX)]
    assert "seo.noindex.in-sitemap" not in ids(site.run(pages, [f"{SITE}/other"]))


def test_indexable_page_in_sitemap_is_fine():
    pages = [page("/a", extra_head=INDEX_OK)]
    assert "seo.noindex.in-sitemap" not in ids(site.run(pages, [f"{SITE}/a"]))


def test_googlebot_directive_is_also_detected():
    pages = [page("/a", extra_head=GOOGLEBOT_NOINDEX)]
    assert "seo.noindex.in-sitemap" in ids(site.run(pages, [f"{SITE}/a"]))


def test_noindex_matching_is_token_based_not_substring():
    # "noindexing" is not the noindex directive
    pages = [page("/a", extra_head='<meta name="robots" content="noindexing">')]
    assert "seo.noindex.in-sitemap" not in ids(site.run(pages, [f"{SITE}/a"]))


def test_sitemap_urls_omitted_means_the_gate_does_not_run():
    pages = [page("/a", extra_head=NOINDEX)]
    assert "seo.noindex.in-sitemap" not in ids(site.run(pages)), (
        "without a sitemap there is nothing to contradict")


def test_trailing_slash_difference_still_matches():
    pages = [page("/a", extra_head=NOINDEX)]
    assert "seo.noindex.in-sitemap" in ids(site.run(pages, [f"{SITE}/a/"]))


def canon(target: str) -> str:
    return f'<link rel="canonical" href="{target}">'


def test_self_canonical_pages_are_fine():
    pages = [page("/a", title="A", extra_head=canon(f"{SITE}/a")),
             page("/b", title="B", extra_head=canon(f"{SITE}/b"))]
    assert "seo.canonical.chained" not in ids(site.run(pages))


def test_a_canonical_chain_is_flagged():
    # /a -> /b, /b -> /c : following one hop from /a lands on a page that is
    # itself canonicalised elsewhere
    pages = [page("/a", title="A", extra_head=canon(f"{SITE}/b")),
             page("/b", title="B", extra_head=canon(f"{SITE}/c")),
             page("/c", title="C", extra_head=canon(f"{SITE}/c"))]
    found = [f for f in site.run(pages) if f.id == "seo.canonical.chained"]
    assert found and found[0].severity == "warning"
    assert found[0].gate == "canonical-cluster"
    assert f"{SITE}/a" == found[0].url


def test_a_single_hop_to_a_self_canonical_target_is_fine():
    pages = [page("/a", title="A", extra_head=canon(f"{SITE}/b")),
             page("/b", title="B", extra_head=canon(f"{SITE}/b"))]
    assert "seo.canonical.chained" not in ids(site.run(pages))


def test_canonical_pointing_outside_the_crawled_set_is_not_judged():
    pages = [page("/a", title="A", extra_head=canon("https://elsewhere.example/x"))]
    assert "seo.canonical.chained" not in ids(site.run(pages)), (
        "no evidence about an uncrawled target; never report an unevaluated gate")


def test_missing_canonical_is_left_to_the_per_url_gate():
    assert "seo.canonical.chained" not in ids(site.run([page("/a")]))


def test_trailing_slash_is_normalised_when_matching_targets():
    pages = [page("/a", title="A", extra_head=canon(f"{SITE}/b/")),
             page("/b", title="B", extra_head=canon(f"{SITE}/b"))]
    assert "seo.canonical.chained" not in ids(site.run(pages))


def alts(pairs: list[tuple[str, str]]) -> str:
    return "".join(
        f'<link rel="alternate" hreflang="{lang}" href="{href}">' for lang, href in pairs)


def test_reciprocal_hreflang_is_fine():
    pages = [
        page("/en", title="EN", lang="en",
             extra_head=alts([("en", f"{SITE}/en"), ("bn", f"{SITE}/bn")])),
        page("/bn", title="BN", lang="bn",
             extra_head=alts([("en", f"{SITE}/en"), ("bn", f"{SITE}/bn")])),
    ]
    assert "seo.hreflang.not-reciprocal" not in ids(site.run(pages))


def test_one_way_hreflang_is_flagged():
    pages = [
        page("/en", title="EN", lang="en",
             extra_head=alts([("bn", f"{SITE}/bn")])),
        page("/bn", title="BN", lang="bn"),          # declares nothing back
    ]
    found = [f for f in site.run(pages) if f.id == "seo.hreflang.not-reciprocal"]
    assert found and found[0].severity == "warning"
    assert found[0].gate == "hreflang-reciprocity"
    assert f"{SITE}/bn" in found[0].observed


def test_alternate_outside_the_crawled_set_is_not_judged():
    pages = [page("/en", title="EN",
                  extra_head=alts([("fr", "https://elsewhere.example/fr")]))]
    assert "seo.hreflang.not-reciprocal" not in ids(site.run(pages))


def test_self_referential_alternate_needs_no_partner():
    pages = [page("/en", title="EN", extra_head=alts([("en", f"{SITE}/en")]))]
    assert "seo.hreflang.not-reciprocal" not in ids(site.run(pages))


def test_x_default_is_exempt_from_reciprocity():
    pages = [
        page("/en", title="EN", extra_head=alts([("x-default", f"{SITE}/en"),
                                                 ("bn", f"{SITE}/bn")])),
        page("/bn", title="BN", extra_head=alts([("en", f"{SITE}/en"),
                                                 ("bn", f"{SITE}/bn")])),
    ]
    findings = [f for f in site.run(pages) if f.id == "seo.hreflang.not-reciprocal"]
    assert findings == [], "x-default is a fallback pointer, not a language pair"


def test_pages_without_hreflang_are_ignored():
    assert "seo.hreflang.not-reciprocal" not in ids(
        site.run([page("/a"), page("/b")]))
