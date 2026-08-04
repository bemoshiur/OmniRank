"""B2/B3/B4: every diff a generator emits must actually apply with real `git
apply`, and the applied file must be byte-correct -- not merely "look right"
in a string comparison.

B2 -- `Path.read_text()` performs universal-newline translation, so the tool
was diffing a string that is not the bytes on disk; every patch against a
CRLF (or lone-CR) file was rejected by `git apply`.

B3 -- `difflib.unified_diff` fabricates a trailing newline instead of emitting
git's `\\ No newline at end of file` marker, so any hunk whose context reaches
EOF was rejected too.

B4 -- inserting a canonical before `</head>` used `rfind("\\n", ...) + 1`,
which is 0 on a single-line document, splicing the tag ahead of
`<!doctype html>` and forcing quirks mode.

This file drives the real `git apply` binary (via tests/_patch.py) rather than
a hand-rolled patcher, across all four MECHANICAL generators, so a diff that
merely LOOKS right cannot pass -- that is exactly how the blockers this file
guards against shipped in the first place.
"""
from __future__ import annotations

from pathlib import Path

from omnirank.fixes import canonical, schema
from omnirank.fixes.base import newline_style, unified_diff
from omnirank.locator import Location
from omnirank.report import Finding

from ._patch import apply_and_read, git_apply_check

PAGE = """<!doctype html>
<html lang="en">
  <head>
    <title>Home</title>
  </head>
  <body><h1>Home</h1></body>
</html>
"""

RELATIVE_CANONICAL_PAGE = PAGE.replace(
    "    <title>Home</title>\n",
    '    <title>Home</title>\n    <link rel="canonical" href="/p/">\n')

CHAINED_CANONICAL_PAGE = PAGE.replace(
    "    <title>Home</title>\n",
    '    <title>Home</title>\n    <link rel="canonical" href="https://x.example/b">\n')

JSONLD_PAGE = """<!doctype html>
<html>
  <head>
    <script type="application/ld+json">
{
  "@type": "Organization",
  "name": "X"
}
    </script>
  </head>
  <body></body>
</html>
"""


def canonical_finding(**kw) -> Finding:
    base = dict(id="seo.canonical.missing", severity="error", layer="seo",
                url="https://x.example/", gate="canonical",
                observed="no rel=canonical",
                expected="one absolute self-referencing canonical",
                fix='Add <link rel="canonical" href="https://x.example/"> to <head>.')
    base.update(kw)
    return Finding(**base)


def chained_finding(**kw) -> Finding:
    base = dict(
        id="seo.canonical.chained", severity="warning", layer="seo",
        url="https://x.example/a", gate="canonical-cluster",
        observed=("canonical points to https://x.example/b, which itself "
                  "canonicalises to https://x.example/c"),
        expected="a canonical pointing directly at a self-canonical page",
        fix="Point this page's canonical straight at https://x.example/c.")
    base.update(kw)
    return Finding(**base)


def schema_finding(**kw) -> Finding:
    base = dict(id="seo.schema.no-context", severity="warning", layer="seo",
                url="https://x.example/", gate="schema",
                observed="Organization node without @context",
                expected='an @context of "https://schema.org"',
                fix="Add @context, or nest the node inside a block that declares it.")
    base.update(kw)
    return Finding(**base)


def write_bytes(tmp_path: Path, name: str, data: bytes) -> Location:
    path = tmp_path / name
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(data)
    return Location(path=name, line=3, confidence="exact")


def to_crlf(text: str) -> bytes:
    return text.replace("\n", "\r\n").encode("utf-8")


def to_lone_cr(text: str) -> bytes:
    return text.replace("\n", "\r").encode("utf-8")


def assert_applies_correctly(tmp_path: Path, relative: str, diff: str):
    """`git apply --check` passes, and applying it does not raise. Returns the
    resulting bytes for the caller's own content assertions."""
    check = git_apply_check(tmp_path, diff)
    assert check.returncode == 0, check.stderr.decode()
    return apply_and_read(tmp_path, relative, diff)


# -- newline_style() -----------------------------------------------------

def test_newline_style_detects_crlf_lf_and_lone_cr():
    assert newline_style("a\r\nb\r\n") == "\r\n"
    assert newline_style("a\rb\r") == "\r"
    assert newline_style("a\nb\n") == "\n"
    assert newline_style("no breaks at all") == "\n"


def test_newline_style_prefers_crlf_over_a_stray_lone_cr_match():
    # "\r\n" contains "\r" as a substring -- CRLF must be checked first so a
    # CRLF file is never misclassified as lone-CR.
    assert newline_style("a\r\nb\r\n") == "\r\n"


# -- B3: no trailing newline, in isolation --------------------------------

def test_unified_diff_marks_missing_trailing_newline_git_style():
    diff = unified_diff("a.txt", "one\ntwo", "one\nTWO")
    assert "\\ No newline at end of file" in diff


def test_unified_diff_no_marker_when_both_sides_have_trailing_newlines():
    diff = unified_diff("a.txt", "one\ntwo\n", "one\nTWO\n")
    assert "\\ No newline at end of file" not in diff


# -- canonical.missing() across newline / trailing-newline / minification --

def test_missing_lf_file_applies_and_is_unchanged_in_style(tmp_path):
    location = write_bytes(tmp_path, "index.html", PAGE.encode())
    made = canonical.missing(canonical_finding(), location, tmp_path, 1, [])
    assert made.fixed, made.reason
    applied = assert_applies_correctly(tmp_path, "index.html", made.diff)
    assert b"\r" not in applied
    assert b'<link rel="canonical" href="https://x.example/">\n' in applied


def test_missing_crlf_file_applies_and_stays_crlf_throughout(tmp_path):
    location = write_bytes(tmp_path, "index.html", to_crlf(PAGE))
    made = canonical.missing(canonical_finding(), location, tmp_path, 1, [])
    assert made.fixed, made.reason
    applied = assert_applies_correctly(tmp_path, "index.html", made.diff)

    # every physical line -- including the newly-inserted one -- ends "\r\n"
    body = applied[:-2] if applied.endswith(b"\r\n") else applied
    for piece in body.split(b"\r\n"):
        assert b"\n" not in piece and b"\r" not in piece
    assert b'<link rel="canonical" href="https://x.example/">\r\n' in applied


def test_missing_lone_cr_file_applies_inline_before_head_close(tmp_path):
    # A lone-CR file has no "\n" anywhere, so `rfind("\n", ...)` -- same as for
    # a genuinely single-line document -- finds none: the whole file reads as
    # one "line" to the </head>-insertion logic too, correctly triggering the
    # SAME inline-splice path B4 uses for a minified single-line document,
    # rather than a new CR-terminated line with its own indent.
    location = write_bytes(tmp_path, "index.html", to_lone_cr(PAGE))
    made = canonical.missing(canonical_finding(), location, tmp_path, 1, [])
    assert made.fixed, made.reason
    applied = assert_applies_correctly(tmp_path, "index.html", made.diff)
    assert b"\n" not in applied
    assert b'<link rel="canonical" href="https://x.example/"></head>' in applied


def test_missing_no_trailing_newline_applies_and_stays_newline_free(tmp_path):
    no_trailing = PAGE.rstrip("\n")
    location = write_bytes(tmp_path, "index.html", no_trailing.encode())
    made = canonical.missing(canonical_finding(), location, tmp_path, 1, [])
    assert made.fixed, made.reason
    applied = assert_applies_correctly(tmp_path, "index.html", made.diff)
    assert not applied.endswith(b"\n")
    assert b'<link rel="canonical" href="https://x.example/">' in applied


def test_missing_tabs_indented_file_applies_and_matches_tab_style(tmp_path):
    tabbed = PAGE.replace("    <title>", "\t<title>").replace("  <head>", "\t<head>")
    location = write_bytes(tmp_path, "index.html", tabbed.encode())
    made = canonical.missing(canonical_finding(), location, tmp_path, 1, [])
    assert made.fixed, made.reason
    applied = assert_applies_correctly(tmp_path, "index.html", made.diff)
    assert b'\t<link rel="canonical" href="https://x.example/">\n' in applied


def test_missing_minified_single_line_inserts_inside_head_after_doctype(tmp_path):
    # B4: a single-line document has no "\n" before </head> at all, so the old
    # `rfind("\n", ...) + 1 == 0` spliced the tag before <!doctype html>.
    minified = "<!doctype html><html><head><title>T</title></head><body>hi</body></html>"
    location = write_bytes(tmp_path, "index.html", minified.encode())
    made = canonical.missing(canonical_finding(), location, tmp_path, 1, [])
    assert made.fixed, made.reason
    applied = assert_applies_correctly(tmp_path, "index.html", made.diff).decode()
    assert applied.startswith("<!doctype html>"), applied
    assert applied.index("<!doctype html>") < applied.index(
        '<link rel="canonical"')
    assert applied.index('<link rel="canonical"') < applied.index("</head>")
    assert applied.index("<head>") < applied.index('<link rel="canonical"')


def test_missing_head_on_one_line_with_content_inserts_inside_head(tmp_path):
    # The milder B4 variant: </head> shares its line with other content in an
    # otherwise multi-line document.
    doc = ('<!doctype html>\n<html lang="en">\n'
           "  <head><title>T</title></head>\n  <body></body>\n</html>\n")
    location = write_bytes(tmp_path, "index.html", doc.encode())
    made = canonical.missing(canonical_finding(), location, tmp_path, 1, [])
    assert made.fixed, made.reason
    applied = assert_applies_correctly(tmp_path, "index.html", made.diff).decode()
    assert applied.startswith("<!doctype html>\n")
    head_line = next(line for line in applied.splitlines() if "</head>" in line)
    assert head_line.index("<head>") < head_line.index('<link rel="canonical"')
    assert head_line.index('<link rel="canonical"') < head_line.index("</head>")
    # never between <html> and <head>
    assert applied.index("<head>") > applied.index("<html")


def test_missing_multiline_document_is_unchanged_from_todays_behaviour(tmp_path):
    location = write_bytes(tmp_path, "index.html", PAGE.encode())
    made = canonical.missing(canonical_finding(), location, tmp_path, 1, [])
    assert made.fixed, made.reason
    added = [line for line in made.diff.splitlines()
             if line.startswith("+") and not line.startswith("+++")]
    assert added == ['+    <link rel="canonical" href="https://x.example/">']


# -- canonical.relative() / .chained() -- href rewrite, no new lines --------

def test_relative_crlf_file_applies_and_stays_crlf(tmp_path):
    location = write_bytes(tmp_path, "pricing.html", to_crlf(RELATIVE_CANONICAL_PAGE))
    made = canonical.relative(
        canonical_finding(id="seo.canonical.relative", url="https://x.example/pricing",
                          observed="relative canonical '/p/'"),
        location, tmp_path, 1, [])
    assert made.fixed, made.reason
    applied = assert_applies_correctly(tmp_path, "pricing.html", made.diff)
    assert b"\n" not in applied.replace(b"\r\n", b"")
    assert b'href="https://x.example/p/"' in applied


def test_relative_no_trailing_newline_applies(tmp_path):
    body = RELATIVE_CANONICAL_PAGE.rstrip("\n")
    location = write_bytes(tmp_path, "pricing.html", body.encode())
    made = canonical.relative(
        canonical_finding(id="seo.canonical.relative", url="https://x.example/pricing",
                          observed="relative canonical '/p/'"),
        location, tmp_path, 1, [])
    assert made.fixed, made.reason
    applied = assert_applies_correctly(tmp_path, "pricing.html", made.diff)
    assert not applied.endswith(b"\n")


def test_chained_crlf_file_applies_and_stays_crlf(tmp_path):
    location = write_bytes(tmp_path, "a.html", to_crlf(CHAINED_CANONICAL_PAGE))
    made = canonical.chained(chained_finding(), location, tmp_path, 1, [])
    assert made.fixed, made.reason
    applied = assert_applies_correctly(tmp_path, "a.html", made.diff)
    assert b'href="https://x.example/c"' in applied
    assert b"\n" not in applied.replace(b"\r\n", b"")


def test_chained_lone_cr_file_applies(tmp_path):
    location = write_bytes(tmp_path, "a.html", to_lone_cr(CHAINED_CANONICAL_PAGE))
    made = canonical.chained(chained_finding(), location, tmp_path, 1, [])
    assert made.fixed, made.reason
    applied = assert_applies_correctly(tmp_path, "a.html", made.diff)
    assert b"\n" not in applied
    assert b'href="https://x.example/c"' in applied


# -- schema.no_context() ----------------------------------------------------

def test_no_context_crlf_file_declines_safely_rather_than_editing_the_wrong_bytes(tmp_path):
    # A pre-existing, separate limitation surfaced by this verification pass
    # (not one of the five blockers): HTML5 parsing mandates newline
    # normalisation inside a <script> body, so BeautifulSoup/lxml hands back
    # `\r\n`/`\r`-free text from `Tag.string` no matter what is on disk. The
    # generator's own byte-exact-match guard (`text.count(raw) != 1`) then sees
    # zero matches against the still-CRLF `text` it read and declines --
    # correctly refusing to guess rather than editing a location it cannot
    # prove is right. Safe, if less helpful than a match would be; recorded
    # here rather than silently assumed to work.
    location = write_bytes(tmp_path, "index.html", to_crlf(JSONLD_PAGE))
    made = schema.no_context(schema_finding(), location, tmp_path, 1, [])
    assert not made.fixed
    assert "byte-exact" in made.reason


def test_no_context_lone_cr_file_declines_safely_rather_than_editing_the_wrong_bytes(tmp_path):
    location = write_bytes(tmp_path, "index.html", to_lone_cr(JSONLD_PAGE))
    made = schema.no_context(schema_finding(), location, tmp_path, 1, [])
    assert not made.fixed
    assert "byte-exact" in made.reason


def test_no_context_no_trailing_newline_applies(tmp_path):
    body = JSONLD_PAGE.rstrip("\n")
    location = write_bytes(tmp_path, "index.html", body.encode())
    made = schema.no_context(schema_finding(), location, tmp_path, 1, [])
    assert made.fixed, made.reason
    applied = assert_applies_correctly(tmp_path, "index.html", made.diff)
    assert not applied.endswith(b"\n")
