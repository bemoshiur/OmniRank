from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

from .config import Config, ConfigError

Unit = Literal["words", "chars"]

# Languages whose scripts do NOT delimit words with spaces. str.split() returns a
# single token for an entire paragraph in these, so word counting is meaningless
# and character counting is the only honest measure.
_NO_WORD_SEPARATOR = {
    "zh", "ja", "ko", "th", "lo", "km", "my", "bo", "dz",
}

# Space-delimited scripts. Word counting works; only the comfortable range differs.
_BRAHMIC = {"bn", "hi", "ta", "te", "kn", "ml", "gu", "pa", "or", "si", "ne", "as", "mr"}
_ARABIC = {"ar", "fa", "ur", "ps", "sd", "ku"}
_CYRILLIC = {"ru", "uk", "bg", "sr", "mk", "be", "kk", "ky", "mn", "tg"}


@dataclass(frozen=True)
class Band:
    unit: Unit
    minimum: int
    maximum: int

    def describe(self) -> str:
        noun = "words" if self.unit == "words" else "characters"
        return f"{self.minimum}-{self.maximum} {noun}"

    def contains(self, value: int) -> bool:
        return self.minimum <= value <= self.maximum


DEFAULT_BAND = Band("words", 40, 60)

# CJK answers carry far more meaning per character; ~80-200 characters is the rough
# equivalent of a 40-60 word English paragraph. Sites should tune this per content.
_BUILTIN_BY_SCRIPT: dict[str, Band] = {
    "cjk": Band("chars", 80, 200),
}


def script_of(lang: str | None) -> str:
    """Map a BCP-47 language tag to a script family. Unknown tags assume latin."""
    if not lang:
        return "latin"
    primary = lang.strip().lower().split("-")[0]
    if primary in _NO_WORD_SEPARATOR:
        return "cjk"
    if primary in _BRAHMIC:
        return "brahmic"
    if primary in _ARABIC:
        return "arabic"
    if primary in _CYRILLIC:
        return "cyrillic"
    return "latin"


def _band_from(raw: dict, path: str) -> Band:
    band = Band(raw["unit"], raw["min"], raw["max"])
    if band.minimum > band.maximum:
        raise ConfigError(
            f"{path} has min {band.minimum} greater than max {band.maximum}"
        )
    return band


def resolve_band(lang: str | None, config: Config) -> Band:
    """The band for this page.

    Precedence, most specific first:
      1. config aeo.answerBlock.byScript[script]  — explicit per-script override
      2. builtin band for that script             — script-specific, beats a
                                                    script-agnostic default
      3. config aeo.answerBlock.default           — the site's own general band
      4. DEFAULT_BAND

    A builtin outranks the config default deliberately: `default` is
    script-agnostic, and a words band cannot validly apply to a script with no
    word separators. A site that genuinely wants to override CJK sets
    byScript.cjk explicitly.
    """
    answer_block = config.raw.get("aeo", {}).get("answerBlock", {})
    script = script_of(lang)

    by_script = answer_block.get("byScript", {})
    if script in by_script:
        return _band_from(by_script[script], f"aeo.answerBlock.byScript.{script}")

    if script in _BUILTIN_BY_SCRIPT:
        return _BUILTIN_BY_SCRIPT[script]

    if "default" in answer_block:
        return _band_from(answer_block["default"], "aeo.answerBlock.default")

    return DEFAULT_BAND


def measure(text: str, band: Band) -> int:
    """Size of `text` in the band's unit. Characters exclude whitespace."""
    if band.unit == "chars":
        return len("".join(text.split()))
    return len(text.split())
