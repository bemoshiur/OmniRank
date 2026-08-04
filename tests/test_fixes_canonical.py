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
    assert "metadataBase" in made.reason
    assert "v0." not in made.reason, "deferral text must not name a version"


def test_canonical_missing_refuses_a_markdown_location_with_markdown_specific_wording(tmp_path):
    # S3: the TSX paragraph talks about `metadata.alternates.canonical` and
    # `metadataBase` -- Next.js App Router concepts that do not exist for a
    # Jekyll/Hugo `.md` source page. Showing it there is actively misleading,
    # not merely irrelevant to the framework actually in play.
    location = write(tmp_path, "pricing.md", "---\nlayout: page\n---\n# Pricing\n")
    made = canonical.missing(finding(), location, tmp_path, 1, [])
    assert not made.fixed
    assert "metadataBase" not in made.reason
    assert "metadata.alternates.canonical" not in made.reason
    assert "markdown" in made.reason.lower()
    assert "v0." not in made.reason


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


def test_canonical_relative_ignores_a_decoy_canonical_inside_an_html_comment(tmp_path):
    # S2: BeautifulSoup parses a commented-out <link> as a Comment node, never
    # a Tag -- it correctly picks the REAL tag. The old `_replace_href` used a
    # raw regex search that matched the textually-first <link rel=canonical>,
    # comment or not, so a decoy sitting in a comment BEFORE the real tag got
    # rewritten while the real tag was left untouched -- and the tool still
    # reported success.
    body = PAGE.replace(
        "    <title>Home</title>\n",
        '    <title>Home</title>\n'
        '    <!-- <link rel="canonical" href="/decoy/"> -->\n'
        '    <link rel="canonical" href="/p/">\n')
    location = write(tmp_path, "pricing.html", body)
    made = canonical.relative(
        finding(id="seo.canonical.relative", url="https://x.example/pricing",
                observed="relative canonical '/p/'"),
        location, tmp_path, 1, [])
    assert made.fixed, made.reason
    changed = [line for line in made.diff.splitlines()
               if line.startswith(("+", "-")) and not line.startswith(("+++", "---"))]
    assert changed == ['-    <link rel="canonical" href="/p/">',
                       '+    <link rel="canonical" href="https://x.example/p/">']
    assert not any("decoy" in line for line in changed)


def test_canonical_chained_ignores_a_decoy_canonical_inside_an_html_comment(tmp_path):
    body = CHAINED_PAGE.replace(
        '    <link rel="canonical" href="https://x.example/b">\n',
        '    <!-- <link rel="canonical" href="https://x.example/decoy"> -->\n'
        '    <link rel="canonical" href="https://x.example/b">\n')
    location = write(tmp_path, "a.html", body)
    made = canonical.chained(chained_finding(), location, tmp_path, 1, [])
    assert made.fixed, made.reason
    changed = [line for line in made.diff.splitlines()
               if line.startswith(("+", "-")) and not line.startswith(("+++", "---"))]
    assert changed == ['-    <link rel="canonical" href="https://x.example/b">',
                       '+    <link rel="canonical" href="https://x.example/c">']
    assert not any("decoy" in line for line in changed)


def test_a_missing_file_declines_rather_than_raising(tmp_path):
    made = canonical.missing(
        finding(), Location(path="gone.html", confidence="exact"), tmp_path, 1, [])
    assert not made.fixed
    assert "could not be read" in made.reason


def test_the_fixes_package_never_writes():
    """No call in omnirank/fixes may create, modify or delete a file.

    Checked against the parsed AST rather than the raw text: a substring scan for
    "open(" also rejects `path.open("r")`, which writes nothing, and would equally
    have been satisfied by the word appearing in a comment. The invariant is about
    what the code CALLS, so ask the syntax tree.
    """
    import ast

    forbidden_attrs = {
        "write_text", "write_bytes", "mkdir", "unlink", "rmdir", "rename",
        "replace", "touch", "symlink_to", "hardlink_to", "chmod",
    }
    forbidden_names = {"rmtree", "copy", "copy2", "copyfile", "move", "remove"}
    write_modes = set("wax+")

    package = Path(__file__).resolve().parents[1] / "scripts" / "py" / "omnirank" / "fixes"
    offences: list[str] = []

    for path in sorted(package.glob("*.py")):
        tree = ast.parse(path.read_text(), filename=str(path))
        for node in ast.walk(tree):
            if not isinstance(node, ast.Call):
                continue
            func = node.func
            name = func.attr if isinstance(func, ast.Attribute) else getattr(func, "id", "")

            if name in forbidden_attrs or name in forbidden_names:
                offences.append(f"{path.name}:{node.lineno} calls {name}()")

            # open()/Path.open() are allowed, but only in a read mode.
            # The mode is args[0] for `p.open(mode)` and args[1] for `open(path, mode)`
            # -- getting that index wrong silently stops this check finding anything.
            if name == "open":
                mode = ""
                index = 0 if isinstance(func, ast.Attribute) else 1
                if len(node.args) > index:
                    arg = node.args[index]
                    if isinstance(arg, ast.Constant) and isinstance(arg.value, str):
                        mode = arg.value
                for kw in node.keywords:
                    if kw.arg == "mode" and isinstance(kw.value, ast.Constant):
                        mode = str(kw.value.value)
                if write_modes & set(mode):
                    offences.append(f"{path.name}:{node.lineno} opens with mode {mode!r}")

    assert not offences, (
        "omnirank/fixes must never write; this release only previews diffs:\n  "
        + "\n  ".join(offences))


from omnirank.fixes import GENERATORS, generate   # noqa: E402
from omnirank.gates import site as site_gate      # noqa: E402
from omnirank.page import PageData                # noqa: E402

CHAINED_PAGE = PAGE.replace(
    "    <title>Home</title>\n",
    '    <title>Home</title>\n    <link rel="canonical" href="https://x.example/b">\n')


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


def test_chained_repoints_at_the_terminal_target(tmp_path):
    location = write(tmp_path, "a.html", CHAINED_PAGE)
    made = canonical.chained(chained_finding(), location, tmp_path, 1, [])
    assert made.fixed, made.reason
    assert '-    <link rel="canonical" href="https://x.example/b">' in made.diff
    assert '+    <link rel="canonical" href="https://x.example/c">' in made.diff


def test_chained_declines_when_the_onward_target_is_itself_chained(tmp_path):
    location = write(tmp_path, "a.html", CHAINED_PAGE)
    onward_is_chained = chained_finding(
        url="https://x.example/c",
        observed=("canonical points to https://x.example/d, which itself "
                  "canonicalises to https://x.example/e"))
    made = canonical.chained(chained_finding(), location, tmp_path, 1,
                             [chained_finding(), onward_is_chained])
    assert not made.fixed
    assert "not terminal" in made.reason


def test_chained_declines_when_the_onward_target_cannot_be_recovered(tmp_path):
    location = write(tmp_path, "a.html", CHAINED_PAGE)
    made = canonical.chained(
        chained_finding(observed="something else entirely"), location, tmp_path, 1, [])
    assert not made.fixed
    assert "onward" in made.reason


def test_the_chained_regex_matches_what_the_gate_actually_emits():
    # A coupling test, on purpose: the onward URL exists only in this prose, so
    # rewording gates/site.py must turn this red rather than silently disabling
    # the fix.
    def page(url: str, canonical_href: str) -> PageData:
        html = f'<html><head><link rel="canonical" href="{canonical_href}">' \
               "</head><body></body></html>"
        return PageData(url=url, html=html, status=200, elapsed_ms=1, headers={})

    findings = site_gate.run([
        page("https://x.example/a", "https://x.example/b"),
        page("https://x.example/b", "https://x.example/c"),
        page("https://x.example/c", "https://x.example/c"),
    ])
    chained = [f for f in findings if f.id == "seo.canonical.chained"]
    assert chained, "the gate must still emit seo.canonical.chained"
    assert canonical.onward_target(chained[0].observed) == "https://x.example/c"


def test_generators_cover_exactly_the_mechanical_tier():
    from omnirank.registry import MECHANICAL_IDS

    assert set(GENERATORS) == set(MECHANICAL_IDS)


def test_generate_refuses_anything_that_is_not_safe(tmp_path):
    location = write(tmp_path, "index.html", PAGE)
    made = generate(finding(), location, root=tmp_path, routes_served=9000,
                    findings=[])
    assert not made.fixed
    assert made.applicability == "display-only"
    assert "display-only" in made.reason


def test_generate_refuses_a_finding_with_no_generator(tmp_path):
    location = write(tmp_path, "index.html", PAGE)
    made = generate(finding(id="seo.h1.multiple", gate="h1"), location,
                    root=tmp_path, routes_served=1, findings=[])
    assert not made.fixed
    assert "advisory" in made.reason


def test_generate_produces_a_diff_on_the_happy_path(tmp_path):
    location = write(tmp_path, "index.html", PAGE)
    made = generate(finding(), location, root=tmp_path, routes_served=1, findings=[])
    assert made.fixed, made.reason
    assert made.applicability == "safe"
