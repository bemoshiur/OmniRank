from omnirank.gates import onpage

URL = "https://x.example/"


def run(body: str, html_attrs: str = " lang='en'") -> list:
    return onpage.run(
        f"<!doctype html><html{html_attrs}><head><title>T</title></head>"
        f"<body>{body}</body></html>", URL)


def ids(findings) -> list[str]:
    return [f.id for f in findings]


# --- images ---------------------------------------------------------------

def test_an_img_with_no_alt_attribute_is_a_warning():
    found = [f for f in run("<img src='a.png'>") if f.id == "seo.image-alt.missing"]
    assert len(found) == 1
    assert found[0].severity == "warning"
    assert found[0].layer == "seo"
    assert found[0].gate == "image-alt"
    assert "a.png" in found[0].observed


def test_an_empty_alt_is_a_legitimate_decorative_marker_and_is_never_flagged():
    assert "seo.image-alt.missing" not in ids(run("<img src='a.png' alt=''>")), (
        'alt="" is how the spec says an image is decorative; flagging it would '
        "tell users to make their markup worse")


def test_explicit_decorative_markers_suppress_the_finding():
    for marker in ("role='presentation'", "role='none'", "aria-hidden='true'"):
        assert "seo.image-alt.missing" not in ids(run(f"<img src='a.png' {marker}>")), marker


def test_one_finding_per_page_naming_the_first_few_sources():
    found = [f for f in run("<img src='a.png'><img src='b.png'><img src='c.png'>")
             if f.id == "seo.image-alt.missing"]
    assert len(found) == 1
    assert "3" in found[0].observed
    assert "a.png" in found[0].observed


# --- heading order --------------------------------------------------------

def test_h1_to_h3_with_no_h2_is_a_warning():
    found = [f for f in run("<h1>A</h1><h3>B</h3>") if f.id == "seo.heading-order.skipped"]
    assert len(found) == 1
    assert found[0].severity == "warning"
    assert found[0].gate == "heading-order"
    assert "h1" in found[0].observed and "h3" in found[0].observed


def test_a_contiguous_outline_passes():
    assert "seo.heading-order.skipped" not in ids(run("<h1>A</h1><h2>B</h2><h3>C</h3>"))


def test_descending_more_than_one_level_is_not_a_skip():
    # h3 -> h1 closes two sections; only an INCREASE of more than one skips a level.
    assert "seo.heading-order.skipped" not in ids(run("<h1>A</h1><h2>B</h2><h3>C</h3><h1>D</h1>"))


def test_only_the_first_skip_is_reported():
    found = [f for f in run("<h1>A</h1><h3>B</h3><h2>C</h2><h4>D</h4>")
             if f.id == "seo.heading-order.skipped"]
    assert len(found) == 1, "one finding per page; the outline is fixed once"


def test_a_page_with_no_headings_emits_no_order_finding():
    assert "seo.heading-order.skipped" not in ids(run("<p>text</p>"))


# --- link text ------------------------------------------------------------

def test_a_link_with_no_accessible_name_is_a_warning():
    found = [f for f in run("<a href='/a'></a>") if f.id == "seo.link-text.empty"]
    assert len(found) == 1
    assert found[0].severity == "warning"
    assert found[0].gate == "link-text"


def test_generic_anchor_text_is_info_and_says_it_is_english_only():
    found = [f for f in run("<a href='/a'>click here</a>")
             if f.id == "seo.link-text.generic"]
    assert len(found) == 1
    assert found[0].severity == "info", (
        "the word list is English-only, so this must never fail a build")
    assert "English" in found[0].fix


def test_generic_matching_ignores_case_and_surrounding_whitespace():
    for text in ("Click Here", "  READ MORE  ", "Learn more"):
        assert "seo.link-text.generic" in ids(run(f"<a href='/a'>{text}</a>")), text


def test_descriptive_anchor_text_passes():
    assert ids(run("<a href='/pricing'>OmniRank pricing plans</a>")) == []


def test_an_aria_label_supplies_the_accessible_name():
    assert "seo.link-text.empty" not in ids(run("<a href='/a' aria-label='Pricing'></a>"))


def test_an_image_alt_inside_the_link_supplies_the_accessible_name():
    assert "seo.link-text.empty" not in ids(
        run("<a href='/a'><img src='i.png' alt='Pricing'></a>"))


def test_links_inside_nav_are_exempt():
    # Navigation labels are terse by design and their context comes from the nav
    # itself; flagging them is noise that trains users to ignore the report.
    assert ids(run("<nav><a href='/a'>more</a><a href='/b'></a></nav>")) == []


def test_an_anchor_with_no_href_is_not_a_link():
    assert ids(run("<a>here</a>")) == []


def test_link_findings_are_one_per_page_per_condition():
    found = run("<a href='/a'>click here</a><a href='/b'>read more</a>"
                "<a href='/c'></a><a href='/d'></a>")
    assert sorted(ids(found)) == ["seo.link-text.empty", "seo.link-text.generic"]


# --- lang -----------------------------------------------------------------

def test_html_without_lang_is_an_error():
    found = [f for f in run("<p>x</p>", html_attrs="") if f.id == "seo.lang.missing"]
    assert len(found) == 1
    assert found[0].severity == "error"
    assert found[0].gate == "lang"
    assert "answer-block" in found[0].fix or "band" in found[0].fix, (
        "the fix must say why this is an error: page.lang drives band selection, "
        "so its absence makes another gate emit a wrong finding")


def test_an_empty_lang_attribute_counts_as_missing():
    assert "seo.lang.missing" in ids(run("<p>x</p>", html_attrs=" lang='  '"))


def test_a_present_lang_passes():
    assert "seo.lang.missing" not in ids(run("<p>x</p>", html_attrs=" lang='bn-BD'"))


def test_a_fully_clean_page_emits_nothing():
    assert onpage.run(
        "<!doctype html><html lang='en'><head><title>T</title></head><body>"
        "<h1>A</h1><h2>B</h2><img src='i.png' alt='A chart'>"
        "<a href='/pricing'>OmniRank pricing</a></body></html>", URL) == []
