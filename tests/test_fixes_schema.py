from pathlib import Path

from omnirank.fixes import schema
from omnirank.locator import Location
from omnirank.report import Finding

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
