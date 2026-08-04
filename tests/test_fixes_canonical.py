from pathlib import Path

import pytest

from omnirank.fixes import canonical
from omnirank.fixes.base import FixOutcome, outcome, quote_char, unified_diff
from omnirank.locator import Location
from omnirank.report import Finding

PAGE = """<!doctype html>
<html lang="en">
  <head>
    <title>Home</title>
  </head>
  <body><h1>Home</h1></body>
</html>
"""

WITH_CANONICAL = PAGE.replace(
    "    <title>Home</title>\n",
    '    <title>Home</title>\n    <link rel="canonical" href="/">\n')

SINGLE_QUOTED = """<!doctype html>
<html lang='en'>
  <head>
    <meta charset='utf-8'>
  </head>
  <body></body>
</html>
"""

SELF_CLOSING = """<!doctype html>
<html lang="en">
  <head>
    <link rel="stylesheet" href="/a.css" />
  </head>
  <body></body>
</html>
"""


def finding(**kw) -> Finding:
    base = dict(id="seo.canonical.missing", severity="error", layer="seo",
                url="https://x.example/", gate="canonical",
                observed="no rel=canonical",
                expected="one absolute self-referencing canonical",
                fix='Add <link rel="canonical" href="https://x.example/"> to <head>.')
    base.update(kw)
    return Finding(**base)


def write(tmp_path: Path, name: str, body: str) -> Location:
    path = tmp_path / name
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(body)
    return Location(path=name, line=3, confidence="exact")


def test_fix_outcome_demands_exactly_one_of_diff_or_reason():
    with pytest.raises(ValueError):
        FixOutcome(finding_id="x.y.z", url="u", fix_tier="mechanical",
                   applicability="safe", path="p", diff=None, reason=None)
    with pytest.raises(ValueError):
        FixOutcome(finding_id="x.y.z", url="u", fix_tier="mechanical",
                   applicability="safe", path="p", diff="d", reason="r")


def test_outcome_helper_carries_the_findings_tier():
    made = outcome(finding(), Location(path="index.html", confidence="exact"),
                   reason="nope")
    assert made.fix_tier == "mechanical"
    assert made.applicability == "safe"
    assert made.fixed is False
    assert made.to_dict()["reason"] == "nope"
    assert "diff" not in made.to_dict()


def test_unified_diff_is_empty_when_nothing_changed():
    assert unified_diff("a.html", "x\n", "x\n") == ""


def test_unified_diff_uses_git_style_prefixes():
    text = unified_diff("index.html", "a\n", "b\n")
    assert text.startswith("--- a/index.html\n+++ b/index.html\n")
    assert text.endswith("\n")


def test_unified_diff_terminates_every_line_even_without_a_trailing_newline():
    text = unified_diff("a.html", "one", "two")
    assert all(line for line in text.splitlines())
    assert text.endswith("\n")


def test_quote_char_follows_the_file():
    assert quote_char(PAGE) == '"'
    assert quote_char(SINGLE_QUOTED) == "'"


def added_lines(diff: str) -> list[str]:
    return [line for line in diff.splitlines()
            if line.startswith("+") and not line.startswith("+++")]


def test_canonical_missing_inserts_before_the_head_close(tmp_path):
    location = write(tmp_path, "index.html", PAGE)
    made = canonical.missing(finding(), location, tmp_path, 1, [])
    assert made.fixed, made.reason
    assert made.diff.startswith("--- a/index.html\n+++ b/index.html\n")
    assert added_lines(made.diff) == [
        '+    <link rel="canonical" href="https://x.example/">']


def test_canonical_missing_matches_local_quote_style(tmp_path):
    location = write(tmp_path, "index.html", SINGLE_QUOTED)
    made = canonical.missing(finding(), location, tmp_path, 1, [])
    assert "+    <link rel='canonical' href='https://x.example/'>" in made.diff


def test_canonical_missing_matches_local_self_closing_style(tmp_path):
    location = write(tmp_path, "index.html", SELF_CLOSING)
    made = canonical.missing(finding(), location, tmp_path, 1, [])
    assert '+    <link rel="canonical" href="https://x.example/" />' in made.diff


def test_canonical_missing_refuses_a_multi_route_file(tmp_path):
    location = write(tmp_path, "index.html", PAGE)
    made = canonical.missing(finding(), location, tmp_path, 412, [])
    assert not made.fixed
    assert "412" in made.reason


def test_canonical_missing_refuses_an_unknown_route_count(tmp_path):
    location = write(tmp_path, "index.html", PAGE)
    made = canonical.missing(finding(), location, tmp_path, None, [])
    assert not made.fixed
    assert "unknown" in made.reason


def test_canonical_missing_is_idempotent_by_detecting_the_existing_tag(tmp_path):
    # Never by a marker comment: users delete markers, and a fixer that
    # duplicates a canonical because its marker was stripped is worse than one
    # that never ran.
    location = write(tmp_path, "index.html", WITH_CANONICAL)
    made = canonical.missing(finding(), location, tmp_path, 1, [])
    assert not made.fixed
    assert "already" in made.reason


def test_canonical_missing_refuses_a_tsx_location(tmp_path):
    location = write(tmp_path, "app/page.tsx", "export default function P() {}\n")
    made = canonical.missing(finding(), location, tmp_path, 1, [])
    assert not made.fixed
    assert "v0.4.0" in made.reason


def test_canonical_missing_refuses_a_file_with_no_head(tmp_path):
    location = write(tmp_path, "frag.html", "<div>no head here</div>\n")
    made = canonical.missing(finding(), location, tmp_path, 1, [])
    assert not made.fixed
    assert "</head>" in made.reason


def test_canonical_relative_resolves_against_the_page_url(tmp_path):
    body = PAGE.replace("    <title>Home</title>\n",
                        '    <title>Home</title>\n    <link rel="canonical" href="/p/">\n')
    location = write(tmp_path, "pricing.html", body)
    made = canonical.relative(
        finding(id="seo.canonical.relative", url="https://x.example/pricing",
                observed="relative canonical '/p/'"),
        location, tmp_path, 1, [])
    assert made.fixed, made.reason
    assert '-    <link rel="canonical" href="/p/">' in made.diff
    assert '+    <link rel="canonical" href="https://x.example/p/">' in made.diff


def test_canonical_relative_preserves_every_other_byte(tmp_path):
    body = PAGE.replace("    <title>Home</title>\n",
                        '    <title>Home</title>\n    <link rel="canonical" href="/p/">\n')
    location = write(tmp_path, "pricing.html", body)
    made = canonical.relative(
        finding(id="seo.canonical.relative", url="https://x.example/pricing"),
        location, tmp_path, 1, [])
    changed = [line for line in made.diff.splitlines()
               if line.startswith(("+", "-")) and not line.startswith(("+++", "---"))]
    assert len(changed) == 2, changed


def test_canonical_relative_declines_when_the_canonical_is_already_absolute(tmp_path):
    body = PAGE.replace(
        "    <title>Home</title>\n",
        '    <title>Home</title>\n    <link rel="canonical" href="https://x.example/">\n')
    location = write(tmp_path, "index.html", body)
    made = canonical.relative(
        finding(id="seo.canonical.relative"), location, tmp_path, 1, [])
    assert not made.fixed
    assert "absolute" in made.reason


def test_canonical_relative_declines_when_there_is_no_canonical(tmp_path):
    location = write(tmp_path, "index.html", PAGE)
    made = canonical.relative(
        finding(id="seo.canonical.relative"), location, tmp_path, 1, [])
    assert not made.fixed


def test_a_missing_file_declines_rather_than_raising(tmp_path):
    made = canonical.missing(
        finding(), Location(path="gone.html", confidence="exact"), tmp_path, 1, [])
    assert not made.fixed
    assert "could not be read" in made.reason


def test_the_fixes_package_never_writes():
    source = ""
    package = Path(__file__).resolve().parents[1] / "scripts" / "py" / "omnirank" / "fixes"
    for path in sorted(package.glob("*.py")):
        source += path.read_text()
    for forbidden in ("write_text(", "open(", "shutil", "os.replace", "mkdir("):
        assert forbidden not in source, (
            f"{forbidden} appears in omnirank/fixes -- this release writes nothing")
