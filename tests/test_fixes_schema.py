import json
from pathlib import Path

from bs4 import BeautifulSoup

from omnirank.fixes import schema
from omnirank.html import find_ldjson_scripts
from omnirank.locator import Location
from omnirank.report import Finding

from ._patch import apply_and_read, git_apply_check

SINGLE_NODE = """<!doctype html>
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

TWO_MATCHING_NODES = SINGLE_NODE.replace(
    "  </head>",
    """    <script type="application/ld+json">
{
  "@type": "Organization",
  "name": "Y"
}
    </script>
  </head>""")

GRAPH_NODE = """<!doctype html>
<html>
  <head>
    <script type="application/ld+json">
{
  "@graph": [{"@type": "Organization", "name": "X"}]
}
    </script>
  </head>
  <body></body>
</html>
"""

ALREADY_CONTEXTED = """<!doctype html>
<html>
  <head>
    <script type="application/ld+json">
{
  "@context": "https://schema.org",
  "@type": "Organization"
}
    </script>
  </head>
  <body></body>
</html>
"""


def finding(**kw) -> Finding:
    base = dict(id="seo.schema.no-context", severity="warning", layer="seo",
                url="https://x.example/", gate="schema",
                observed="Organization node without @context",
                expected='an @context of "https://schema.org"',
                fix="Add @context, or nest the node inside a block that declares it.")
    base.update(kw)
    return Finding(**base)


def write(tmp_path: Path, name: str, body: str) -> Location:
    (tmp_path / name).write_text(body)
    return Location(path=name, line=3, confidence="exact")


# -- B1 regression: a compact one-line object must not be destroyed ---------
#
# `_insert_context` used to splice at whichever "\n" came first in the raw
# text. For a compact one-line object that is the newline AFTER the closing
# brace -- not one introduced by pretty-printing -- so the old code discarded
# everything before it: the whole node, closing brace included. The patch
# still applied cleanly and left invalid JSON and an unterminated-looking
# script body. These tests assert on the POST-APPLY file, parsed with
# `json.loads`, not just on the diff text: a diff that looks right and
# destroys the file is exactly what shipped.

COMPACT_ONE_LINE = """<!doctype html>
<html>
  <head>
    <script type="application/ld+json">
{"@type":"Organization","name":"Fixture Co"}
    </script>
  </head>
  <body></body>
</html>
"""

FIRST_MEMBER_SHARES_THE_BRACE_LINE = """<!doctype html>
<html>
  <head>
    <script type="application/ld+json">
{"@type": "Organization",
 "name": "Fixture Co"}
    </script>
  </head>
  <body></body>
</html>
"""


def _applied_node(tmp_path: Path, diff: str) -> dict:
    check = git_apply_check(tmp_path, diff)
    assert check.returncode == 0, check.stderr.decode()
    applied = apply_and_read(tmp_path, "index.html", diff).decode("utf-8")
    soup = BeautifulSoup(applied, "lxml")
    scripts = find_ldjson_scripts(soup)
    assert len(scripts) == 1
    return json.loads(scripts[0].string)


def test_no_context_compact_one_line_object_applies_and_stays_valid_json(tmp_path):
    location = write(tmp_path, "index.html", COMPACT_ONE_LINE)
    made = schema.no_context(finding(), location, tmp_path, 1, [])
    assert made.fixed, made.reason

    node = _applied_node(tmp_path, made.diff)
    assert node["@context"] == "https://schema.org"
    assert node["@type"] == "Organization"
    assert node["name"] == "Fixture Co"


def test_no_context_first_member_sharing_the_brace_line_applies_and_stays_valid(tmp_path):
    # The bug report's own description of the common minified shape: not
    # necessarily the WHOLE object on one line, just its first member sharing
    # the brace's line.
    location = write(tmp_path, "index.html", FIRST_MEMBER_SHARES_THE_BRACE_LINE)
    made = schema.no_context(finding(), location, tmp_path, 1, [])
    assert made.fixed, made.reason

    node = _applied_node(tmp_path, made.diff)
    assert node["@context"] == "https://schema.org"
    assert node["@type"] == "Organization"
    assert node["name"] == "Fixture Co"


def test_no_context_pretty_printed_object_is_unchanged_from_todays_behaviour(tmp_path):
    # The multi-line branch itself must not regress: this is byte-for-byte the
    # existing (correct) fixture and shape used elsewhere in this file.
    location = write(tmp_path, "index.html", SINGLE_NODE)
    made = schema.no_context(finding(), location, tmp_path, 1, [])
    assert made.fixed, made.reason
    added = [line for line in made.diff.splitlines()
             if line.startswith("+") and not line.startswith("+++")]
    assert added == ['+  "@context": "https://schema.org",']

    node = _applied_node(tmp_path, made.diff)
    assert node["@context"] == "https://schema.org"
    assert node["@type"] == "Organization"
    assert node["name"] == "X"


def test_no_context_inserts_the_constant_after_the_opening_brace(tmp_path):
    location = write(tmp_path, "index.html", SINGLE_NODE)
    made = schema.no_context(finding(), location, tmp_path, 1, [])
    assert made.fixed, made.reason
    added = [line for line in made.diff.splitlines()
             if line.startswith("+") and not line.startswith("+++")]
    assert added == ['+  "@context": "https://schema.org",']


def test_no_context_is_idempotent(tmp_path):
    location = write(tmp_path, "index.html", ALREADY_CONTEXTED)
    made = schema.no_context(finding(), location, tmp_path, 1, [])
    assert not made.fixed
    assert "0" in made.reason or "no " in made.reason


def test_no_context_declines_when_two_nodes_share_the_type(tmp_path):
    # The finding carries a @type and no JSON pointer, so two candidates is a
    # genuine ambiguity about WHICH node the gate meant.
    location = write(tmp_path, "index.html", TWO_MATCHING_NODES)
    made = schema.no_context(finding(), location, tmp_path, 1, [])
    assert not made.fixed
    assert "2" in made.reason


def test_no_context_declines_on_a_graph_block(tmp_path):
    location = write(tmp_path, "index.html", GRAPH_NODE)
    made = schema.no_context(finding(), location, tmp_path, 1, [])
    assert not made.fixed


def test_no_context_declines_on_a_multi_typed_node(tmp_path):
    location = write(tmp_path, "index.html", SINGLE_NODE)
    made = schema.no_context(
        finding(observed="['Article', 'BlogPosting'] node without @context"),
        location, tmp_path, 1, [])
    assert not made.fixed
    assert "multi-typed" in made.reason


def test_no_context_declines_when_the_type_cannot_be_read(tmp_path):
    location = write(tmp_path, "index.html", SINGLE_NODE)
    made = schema.no_context(finding(observed="who knows"), location, tmp_path, 1, [])
    assert not made.fixed


def test_no_context_declines_on_a_tsx_location(tmp_path):
    (tmp_path / "page.tsx").write_text("export default function P() {}\n")
    made = schema.no_context(
        finding(), Location(path="page.tsx", confidence="exact"), tmp_path, 1, [])
    assert not made.fixed
    assert "v0.4.0" in made.reason


def test_no_context_preserves_every_other_byte(tmp_path):
    location = write(tmp_path, "index.html", SINGLE_NODE)
    made = schema.no_context(finding(), location, tmp_path, 1, [])
    changed = [line for line in made.diff.splitlines()
               if line.startswith(("+", "-")) and not line.startswith(("+++", "---"))]
    assert len(changed) == 1, changed
