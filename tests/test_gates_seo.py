from pathlib import Path

from omnirank.gates import seo

FIXTURES = Path(__file__).parent / "fixtures"
URL = "https://x.example/services/political-ads"


def clean() -> str:
    return (FIXTURES / "clean.html").read_text()


def ids(findings) -> set[str]:
    return {f.id for f in findings}


def test_clean_page_produces_no_findings():
    assert seo.run(clean(), URL) == []


def test_missing_h1_is_an_error():
    html = clean().replace("<h1>Political Facebook Advertising in Bangladesh</h1>", "")
    found = [f for f in seo.run(html, URL) if f.id == "seo.h1.missing"]
    assert found and found[0].severity == "error"
    assert found[0].gate == "h1"


def test_multiple_h1_is_an_error():
    html = clean().replace("</body>", "<h1>Second</h1></body>")
    found = [f for f in seo.run(html, URL) if f.id == "seo.h1.multiple"]
    assert found and found[0].observed == "2 <h1> elements"


def test_missing_canonical_is_an_error():
    html = clean().replace(
        '<link rel="canonical" href="https://x.example/services/political-ads">', "")
    assert "seo.canonical.missing" in ids(seo.run(html, URL))


def test_relative_canonical_is_an_error():
    html = clean().replace("https://x.example/services/political-ads\">\n  <link rel=\"alternate\"",
                           "/services/political-ads\">\n  <link rel=\"alternate\"")
    assert "seo.canonical.relative" in ids(seo.run(html, URL))


def test_long_title_is_a_warning():
    html = clean().replace(
        "<title>Political Facebook Advertising in Bangladesh</title>",
        f"<title>{'a' * 61}</title>")
    found = [f for f in seo.run(html, URL) if f.id == "seo.title.long"]
    assert found and found[0].severity == "warning"
    assert found[0].gate == "title-length"


def test_missing_title_is_an_error():
    html = clean().replace(
        "<title>Political Facebook Advertising in Bangladesh</title>", "")
    assert "seo.title.missing" in ids(seo.run(html, URL))


def test_long_description_is_a_warning():
    html = clean().replace('content="TICON System Limited runs compliant political Facebook '
                           'campaigns across Bangladesh with transparent BDT reporting and '
                           'verified audience targeting."',
                           f'content="{"a" * 161}"')
    found = [f for f in seo.run(html, URL) if f.id == "seo.description.long"]
    assert found and found[0].gate == "description-length"


def test_missing_og_image_is_a_warning():
    html = clean().replace('<meta property="og:image" content="https://x.example/og.png">', "")
    found = [f for f in seo.run(html, URL) if f.id == "seo.og.missing"]
    assert found and "og:image" in found[0].observed


def test_hreflang_without_x_default_is_a_warning():
    html = clean().replace(
        '<link rel="alternate" hreflang="x-default" '
        'href="https://x.example/services/political-ads">', "")
    assert "seo.hreflang.no-x-default" in ids(seo.run(html, URL))


def test_page_without_hreflang_at_all_is_not_flagged():
    html = clean()
    for tag in ['<link rel="alternate" hreflang="en" '
                'href="https://x.example/services/political-ads">',
                '<link rel="alternate" hreflang="x-default" '
                'href="https://x.example/services/political-ads">']:
        html = html.replace(tag, "")
    assert "seo.hreflang.no-x-default" not in ids(seo.run(html, URL))


def test_image_without_dimensions_is_a_warning():
    html = clean().replace('<img src="/a.png" width="1200" height="630" alt="Campaign dashboard">',
                           '<img src="/a.png" alt="Campaign dashboard">')
    found = [f for f in seo.run(html, URL) if f.id == "seo.image.no-dims"]
    assert found and found[0].gate == "image-dims"


# --- v0.2.1: HTML attribute VALUES are case-insensitive per spec; a differently-
# cased but perfectly valid attribute must never be reported as missing. Each pair
# below reproduces one confirmed false positive, then a companion proving the gate
# still fires when the thing really is absent -- so the suite can tell "fixed" from
# "gate silently disabled" apart. ---

def test_uppercase_meta_description_name_is_not_flagged_missing():
    html = clean().replace('<meta name="description"', '<meta name="Description"')
    assert "seo.description.missing" not in ids(seo.run(html, URL))


def test_meta_description_genuinely_absent_is_still_flagged():
    html = clean().replace(
        '<meta name="description" content="TICON System Limited runs compliant political '
        'Facebook campaigns across Bangladesh with transparent BDT reporting and '
        'verified audience targeting.">', "")
    found = [f for f in seo.run(html, URL) if f.id == "seo.description.missing"]
    assert found and found[0].severity == "error"


def test_uppercase_canonical_rel_is_not_flagged_missing():
    html = clean().replace('<link rel="canonical"', '<link rel="Canonical"')
    assert "seo.canonical.missing" not in ids(seo.run(html, URL))


def test_canonical_genuinely_absent_is_still_flagged():
    html = clean().replace(
        '<link rel="canonical" href="https://x.example/services/political-ads">', "")
    assert "seo.canonical.missing" in ids(seo.run(html, URL))


def test_uppercase_x_default_hreflang_is_not_flagged():
    html = clean().replace('hreflang="x-default"', 'hreflang="X-Default"')
    assert "seo.hreflang.no-x-default" not in ids(seo.run(html, URL))


def test_hreflang_without_any_x_default_is_still_flagged():
    html = clean().replace(
        '<link rel="alternate" hreflang="x-default" '
        'href="https://x.example/services/political-ads">', "")
    assert "seo.hreflang.no-x-default" in ids(seo.run(html, URL))
