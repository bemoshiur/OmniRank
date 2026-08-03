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
