from pathlib import Path

from omnirank.bands import Band
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


def test_fewer_than_three_faqs_is_a_warning():
    # v0.2.1: downgraded from error -- demanding 3+ FAQs on every page (pricing,
    # about, 404s included) is not defensible advice.
    html = clean().replace(
        "<dt>How fast?</dt><dd>Setup completes within five working days.</dd>", "")
    found = [f for f in aeo.run(html, URL) if f.id == "aeo.faq.too-few"]
    assert found and found[0].observed == "2 FAQ pairs"
    assert found[0].gate == "faq"
    assert found[0].severity == "warning"


def test_details_markup_counts_as_faq():
    html = clean()
    start = html.index("<dl>")
    end = html.index("</dl>") + len("</dl>")
    details = "".join(
        f"<details><summary>Q{i}</summary><p>A{i}</p></details>" for i in range(3))
    html = html[:start] + details + html[end:]
    assert "aeo.faq.too-few" not in ids(aeo.run(html, URL))


def test_dt_and_details_pairs_are_summed_not_or_ed():
    # v0.2.1 bug fix: `len(dt) or len(details)` short-circuited on any non-zero
    # <dt> count, so a page with 2 <dt> pairs PLUS 20 real <details>-based FAQs
    # reported only "2 FAQ pairs" (too few) and completely ignored the 20 that
    # were genuinely there. A <dt> is never itself a <details>, so summing both
    # never double-counts a single pair. Under the old code this scenario WOULD
    # (wrongly) fire aeo.faq.too-few; under the fix it correctly does not.
    html = clean().replace(
        "<dt>How fast?</dt><dd>Setup completes within five working days.</dd>", "")
    details = "".join(
        f"<details><summary>Q{i}</summary><p>A{i}</p></details>" for i in range(20))
    html = html.replace("</dl>", "</dl>" + details, 1)
    found = [f for f in aeo.run(html, URL) if f.id == "aeo.faq.too-few"]
    assert not found, "2 dt + 20 details = 22 FAQ pairs, well above the minimum"


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


def block_with_text(text: str) -> str:
    html = clean()
    start = html.index('<div class="answer-block" data-speakable>')
    end = html.index("</div>", start) + len("</div>")
    return (html[:start]
            + f'<div class="answer-block" data-speakable>{text}</div>'
            + html[end:])


def test_exactly_forty_words_passes():
    assert "aeo.answer-block.length" not in ids(aeo.run(block_with(40), URL))


def test_thirty_nine_words_fails():
    assert "aeo.answer-block.length" in ids(aeo.run(block_with(39), URL))


def test_exactly_sixty_words_passes():
    assert "aeo.answer-block.length" not in ids(aeo.run(block_with(60), URL))


def test_sixty_one_words_fails():
    assert "aeo.answer-block.length" in ids(aeo.run(block_with(61), URL))


def test_default_band_is_unchanged_for_existing_callers():
    # 47-word fixture block, inside the default 40-60 band
    assert "aeo.answer-block.length" not in ids(aeo.run(clean(), URL))


def test_explicit_char_band_accepts_a_cjk_block():
    cjk = "这是一个完整的段落" * 12          # 108 characters, 1 whitespace token
    html = block_with_text(cjk)
    findings = ids(aeo.run(html, URL, band=Band("chars", 80, 200)))
    assert "aeo.answer-block.length" not in findings


def test_word_band_would_wrongly_flag_the_same_cjk_block():
    cjk = "这是一个完整的段落" * 12
    html = block_with_text(cjk)
    found = [f for f in aeo.run(html, URL, band=Band("words", 40, 60))
             if f.id == "aeo.answer-block.length"]
    assert found, "demonstrates the bug: split() sees 1 token in 108 CJK characters"
    assert found[0].observed == "1 words"


def test_finding_text_names_the_band_that_was_applied():
    short = block_with_text("far too short")
    found = [f for f in aeo.run(short, URL, band=Band("chars", 80, 200))
             if f.id == "aeo.answer-block.length"]
    assert found and found[0].expected == "80-200 characters"
