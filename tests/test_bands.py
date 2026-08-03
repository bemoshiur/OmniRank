import pytest

from omnirank.bands import DEFAULT_BAND, Band, measure, resolve_band, script_of
from omnirank.config import Config


def cfg(raw=None) -> Config:
    base = {"site": {"name": "X", "url": "https://x.example",
                     "entityType": "Organization"}}
    if raw:
        base.update(raw)
    return Config(base)


@pytest.mark.parametrize("lang,expected", [
    ("en", "latin"), ("en-US", "latin"), ("de", "latin"), ("pt-BR", "latin"),
    ("zh", "cjk"), ("zh-Hans", "cjk"), ("ja", "cjk"), ("ko", "cjk"),
    ("th", "cjk"), ("lo", "cjk"), ("km", "cjk"), ("my", "cjk"),
    ("bn", "brahmic"), ("bn-BD", "brahmic"), ("hi", "brahmic"), ("ta", "brahmic"),
    ("ar", "arabic"), ("fa", "arabic"), ("ur", "arabic"),
    ("ru", "cyrillic"), ("uk", "cyrillic"),
])
def test_script_detection(lang, expected):
    assert script_of(lang) == expected


def test_unknown_and_missing_lang_default_to_latin():
    assert script_of(None) == "latin"
    assert script_of("") == "latin"
    assert script_of("xx-YY") == "latin"


def test_default_band_is_forty_to_sixty_words():
    assert DEFAULT_BAND == Band("words", 40, 60)
    assert resolve_band("en", cfg()) == DEFAULT_BAND


def test_cjk_defaults_to_characters_not_words():
    band = resolve_band("ja", cfg())
    assert band.unit == "chars", (
        "CJK has no word separators; split() returns one token for a whole paragraph")


def test_brahmic_uses_words_because_it_is_space_delimited():
    assert resolve_band("bn-BD", cfg()).unit == "words"


def test_config_default_overrides_builtin():
    c = cfg({"aeo": {"answerBlock": {"default": {"unit": "words", "min": 30, "max": 80}}}})
    assert resolve_band("en", c) == Band("words", 30, 80)


def test_config_by_script_overrides_default():
    c = cfg({"aeo": {"answerBlock": {
        "default": {"unit": "words", "min": 40, "max": 60},
        "byScript": {"brahmic": {"unit": "chars", "min": 200, "max": 400}}}}})
    assert resolve_band("bn", c) == Band("chars", 200, 400)
    assert resolve_band("en", c) == Band("words", 40, 60)


def test_measure_words():
    assert measure("one two three", Band("words", 1, 5)) == 3


def test_measure_chars_ignores_whitespace():
    assert measure("a b  c", Band("chars", 1, 5)) == 3


def test_measure_counts_cjk_characters_not_tokens():
    text = "这是一个完整的段落"
    assert measure(text, Band("words", 1, 5)) == 1, "split() sees one token"
    assert measure(text, Band("chars", 1, 20)) == len(text)


def test_describe_reads_naturally():
    assert Band("words", 40, 60).describe() == "40-60 words"
    assert Band("chars", 80, 200).describe() == "80-200 characters"


def test_inverted_band_from_config_is_rejected():
    import pytest
    from omnirank.config import ConfigError

    c = cfg({"aeo": {"answerBlock": {"default": {"unit": "words", "min": 100, "max": 5}}}})
    with pytest.raises(ConfigError, match="100"):
        resolve_band("en", c)


def test_inverted_by_script_band_is_rejected():
    import pytest
    from omnirank.config import ConfigError

    c = cfg({"aeo": {"answerBlock": {
        "default": {"unit": "words", "min": 40, "max": 60},
        "byScript": {"cjk": {"unit": "chars", "min": 300, "max": 100}}}}})
    with pytest.raises(ConfigError, match="cjk"):
        resolve_band("ja", c)


def test_equal_min_and_max_is_allowed():
    c = cfg({"aeo": {"answerBlock": {"default": {"unit": "words", "min": 50, "max": 50}}}})
    assert resolve_band("en", c) == Band("words", 50, 50)
