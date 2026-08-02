from pathlib import Path

from omnirank.gates import aeo

FIXTURES = Path(__file__).parent / "fixtures"
URL = "https://x.example/services/political-ads"


def clean() -> str:
    return (FIXTURES / "aeo_clean.html").read_text()


def ids(findings) -> set[str]:
    return {f.id for f in findings}


def test_clean_page_produces_no_findings():
    assert aeo.run(clean(), URL) == []


def test_missing_answer_block_is_an_error():
    html = clean().replace('class="answer-block"', 'class="intro"')
    found = [f for f in aeo.run(html, URL) if f.id == "aeo.answer-block.missing"]
    assert found and found[0].severity == "error"
    assert found[0].gate == "answer-block"


def test_short_answer_block_is_an_error():
    html = clean()
    start = html.index('<div class="answer-block" data-speakable>')
    end = html.index("</div>", start) + len("</div>")
    html = html[:start] + '<div class="answer-block" data-speakable>Too short.</div>' + html[end:]
    found = [f for f in aeo.run(html, URL) if f.id == "aeo.answer-block.length"]
    assert found and "2 words" in found[0].observed


def test_long_answer_block_is_an_error():
    html = clean()
    start = html.index('<div class="answer-block" data-speakable>')
    end = html.index("</div>", start) + len("</div>")
    words = " ".join(["word"] * 80)
    html = html[:start] + f'<div class="answer-block" data-speakable>{words}</div>' + html[end:]
    assert "aeo.answer-block.length" in ids(aeo.run(html, URL))


def test_list_markup_inside_answer_block_is_an_error():
    html = clean().replace("</div>", "<ul><li>a</li></ul></div>", 1)
    found = [f for f in aeo.run(html, URL) if f.id == "aeo.answer-block.list-markup"]
    assert found and found[0].severity == "error"


def test_fewer_than_three_faqs_is_an_error():
    html = clean().replace(
        "<dt>How fast?</dt><dd>Setup completes within five working days.</dd>", "")
    found = [f for f in aeo.run(html, URL) if f.id == "aeo.faq.too-few"]
    assert found and found[0].observed == "2 FAQ pairs"
    assert found[0].gate == "faq"


def test_details_markup_counts_as_faq():
    html = clean()
    start = html.index("<dl>")
    end = html.index("</dl>") + len("</dl>")
    details = "".join(
        f"<details><summary>Q{i}</summary><p>A{i}</p></details>" for i in range(3))
    html = html[:start] + details + html[end:]
    assert "aeo.faq.too-few" not in ids(aeo.run(html, URL))


def test_speakable_selector_that_matches_nothing_is_an_error():
    html = clean().replace('".answer-block"', '".does-not-exist"')
    found = [f for f in aeo.run(html, URL) if f.id == "aeo.speakable.unresolved"]
    assert found and found[0].gate == "speakable"


def test_custom_selector_is_honoured():
    html = clean().replace('class="answer-block"', 'class="tldr"')
    assert "aeo.answer-block.missing" not in ids(aeo.run(html, URL, selector=".tldr"))


def block_with(word_count: int) -> str:
    html = clean()
    start = html.index('<div class="answer-block" data-speakable>')
    end = html.index("</div>", start) + len("</div>")
    words = " ".join(["word"] * word_count)
    return html[:start] + f'<div class="answer-block" data-speakable>{words}</div>' + html[end:]


def test_exactly_forty_words_passes():
    assert "aeo.answer-block.length" not in ids(aeo.run(block_with(40), URL))


def test_thirty_nine_words_fails():
    assert "aeo.answer-block.length" in ids(aeo.run(block_with(39), URL))


def test_exactly_sixty_words_passes():
    assert "aeo.answer-block.length" not in ids(aeo.run(block_with(60), URL))


def test_sixty_one_words_fails():
    assert "aeo.answer-block.length" in ids(aeo.run(block_with(61), URL))
