from pathlib import Path

from omnirank.framework import Detection
from omnirank.locator import NOT_LOCATED, Location, locate, route_of

NEXT = Detection("next-app-router", "high", ("next.config.mjs", "app/layout.tsx"))

METADATA_PAGE = """import type { Metadata } from "next";

export const metadata: Metadata = {
  title: "Pricing",
};

export default function Page() {
  return <h1>Pricing</h1>;
}
"""

GENERATE_METADATA_PAGE = """import type { Metadata } from "next";

export async function generateMetadata({ params }): Promise<Metadata> {
  return { title: params.slug };
}

export default function Page() {
  return <h1>Post</h1>;
}
"""

BARE_PAGE = """export default function Page() {
  return <h1>Hello</h1>;
}
"""


def app(tmp_path: Path, pages: dict[str, str]) -> Path:
    tmp_path.mkdir(parents=True, exist_ok=True)   # callers may pass a subdirectory
    (tmp_path / "next.config.mjs").write_text("")
    (tmp_path / "app").mkdir(parents=True, exist_ok=True)
    (tmp_path / "app" / "layout.tsx").write_text("")
    for relative, body in pages.items():
        path = tmp_path / "app" / relative
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(body)
    return tmp_path


def test_route_of_normalises_paths():
    assert route_of("https://x.example/") == "/"
    assert route_of("https://x.example") == "/"
    assert route_of("https://x.example/pricing") == "/pricing"
    assert route_of("https://x.example/pricing/") == "/pricing"
    assert route_of("https://x.example/a/b/?q=1#f") == "/a/b"


def test_root_route_resolves_to_app_page(tmp_path):
    root = app(tmp_path, {"page.tsx": METADATA_PAGE})
    found = locate("https://x.example/", detection=NEXT, root=root)
    assert found.path == "app/page.tsx"
    assert found.confidence == "exact"
    assert found.line == 3, "the line of `export const metadata`"


def test_a_static_nested_route(tmp_path):
    root = app(tmp_path, {"pricing/page.tsx": METADATA_PAGE})
    found = locate("https://x.example/pricing", detection=NEXT, root=root)
    assert found.path == "app/pricing/page.tsx"
    assert found.confidence == "exact"


def test_route_groups_do_not_appear_in_the_url(tmp_path):
    root = app(tmp_path, {"(marketing)/pricing/page.tsx": METADATA_PAGE})
    found = locate("https://x.example/pricing", detection=NEXT, root=root)
    assert found.path == "app/(marketing)/pricing/page.tsx"
    assert found.confidence == "exact"


def test_parallel_slots_are_not_route_segments(tmp_path):
    # `_components/page.tsx` is a decoy here: it must not interfere with the
    # `@modal` match. It is not itself routable -- see the private-folder
    # tests below for that behaviour.
    root = app(tmp_path, {"@modal/settings/page.tsx": METADATA_PAGE,
                          "_components/page.tsx": BARE_PAGE})
    found = locate("https://x.example/settings", detection=NEXT, root=root)
    assert found.path == "app/@modal/settings/page.tsx"


def test_a_private_folder_is_not_a_route_at_all(tmp_path):
    # Next.js opts a `_`-prefixed folder -- and everything beneath it -- out
    # of routing entirely. This is NOT route-group semantics: the page is
    # unreachable by any URL, not merely reachable at a shorter one. A real
    # deployment 404s on `/blog`; the locator must agree, not report `exact`.
    root = app(tmp_path, {"_internal/blog/page.tsx": METADATA_PAGE})
    found = locate("https://x.example/blog", detection=NEXT, root=root)
    assert found == NOT_LOCATED
    assert found.path is None
    assert found.confidence == "none"


def test_the_url_form_of_a_private_folder_is_also_not_routable(tmp_path):
    # Requesting the literal `_`-prefixed path in the URL doesn't make the
    # folder routable either -- there is no URL that reaches it.
    root = app(tmp_path, {"_lib/page.tsx": BARE_PAGE})
    assert locate("https://x.example/_lib", detection=NEXT, root=root) == NOT_LOCATED


def test_a_private_folder_removes_everything_nested_beneath_it(tmp_path):
    # The strongest reproduction: naive segment-stripping would match
    # `blog/_drafts/secret/page.tsx` against `/blog/secret`, since dropping
    # `_drafts` leaves exactly that pattern. The whole subtree is unroutable.
    root = app(tmp_path, {"blog/_drafts/secret/page.tsx": METADATA_PAGE})
    found = locate("https://x.example/blog/secret", detection=NEXT, root=root)
    assert found == NOT_LOCATED


def test_parallel_route_slots_still_resolve_after_the_private_folder_fix(tmp_path):
    root = app(tmp_path, {"@modal/login/page.tsx": METADATA_PAGE})
    found = locate("https://x.example/login", detection=NEXT, root=root)
    assert found.path == "app/@modal/login/page.tsx"
    assert found.confidence == "exact"


def test_route_groups_still_resolve_after_the_private_folder_fix(tmp_path):
    root = app(tmp_path, {"(marketing)/pricing/page.tsx": METADATA_PAGE})
    found = locate("https://x.example/pricing", detection=NEXT, root=root)
    assert found.path == "app/(marketing)/pricing/page.tsx"
    assert found.confidence == "exact"


def test_a_dynamic_segment_is_inferred_not_exact(tmp_path):
    root = app(tmp_path, {"blog/[slug]/page.tsx": METADATA_PAGE})
    found = locate("https://x.example/blog/hello-world", detection=NEXT, root=root)
    assert found.path == "app/blog/[slug]/page.tsx"
    assert found.confidence == "inferred"


def test_a_static_route_wins_over_a_dynamic_one(tmp_path):
    root = app(tmp_path, {"blog/[slug]/page.tsx": METADATA_PAGE,
                          "blog/archive/page.tsx": METADATA_PAGE})
    found = locate("https://x.example/blog/archive", detection=NEXT, root=root)
    assert found.path == "app/blog/archive/page.tsx"
    assert found.confidence == "exact"


def test_a_catch_all_matches_one_or_more_segments(tmp_path):
    root = app(tmp_path, {"docs/[...path]/page.tsx": METADATA_PAGE})
    assert locate("https://x.example/docs/a/b/c", detection=NEXT,
                  root=root).path == "app/docs/[...path]/page.tsx"
    assert locate("https://x.example/docs", detection=NEXT, root=root) == NOT_LOCATED


def test_an_optional_catch_all_matches_zero_segments(tmp_path):
    root = app(tmp_path, {"docs/[[...path]]/page.tsx": METADATA_PAGE})
    assert locate("https://x.example/docs", detection=NEXT,
                  root=root).path == "app/docs/[[...path]]/page.tsx"
    assert locate("https://x.example/docs/a/b", detection=NEXT,
                  root=root).path == "app/docs/[[...path]]/page.tsx"


def test_two_equally_specific_matches_never_guess(tmp_path):
    # Route groups make this legal to write and ambiguous to resolve.
    root = app(tmp_path, {"(a)/promo/page.tsx": METADATA_PAGE,
                          "(b)/promo/page.tsx": METADATA_PAGE})
    assert locate("https://x.example/promo", detection=NEXT, root=root) == NOT_LOCATED


def test_no_matching_route_is_not_located(tmp_path):
    root = app(tmp_path, {"pricing/page.tsx": METADATA_PAGE})
    assert locate("https://x.example/nowhere", detection=NEXT, root=root) == NOT_LOCATED


def test_generate_metadata_reports_the_file_but_refuses_the_edit(tmp_path):
    # The file is certainly right; the value is computed at request time and
    # this tool does not rewrite function bodies. Saying "here, but no" beats
    # saying nothing.
    root = app(tmp_path, {"blog/[slug]/page.tsx": GENERATE_METADATA_PAGE})
    found = locate("https://x.example/blog/hello", detection=NEXT, root=root)
    assert found.path == "app/blog/[slug]/page.tsx"
    assert found.line == 3
    assert found.confidence == "none"


def test_a_page_with_no_metadata_export_is_still_an_exact_location(tmp_path):
    root = app(tmp_path, {"about/page.tsx": BARE_PAGE})
    found = locate("https://x.example/about", detection=NEXT, root=root)
    assert found.path == "app/about/page.tsx"
    assert found.line is None
    assert found.confidence == "exact"


def test_src_app_is_found_too(tmp_path):
    (tmp_path / "next.config.mjs").write_text("")
    page = tmp_path / "src" / "app" / "pricing"
    page.mkdir(parents=True)
    (page / "page.tsx").write_text(METADATA_PAGE)
    found = locate("https://x.example/pricing", detection=NEXT, root=tmp_path)
    assert found.path == "src/app/pricing/page.tsx"


def test_every_page_file_extension_is_recognised(tmp_path):
    for name in ("page.tsx", "page.jsx", "page.ts", "page.js"):
        root = app(tmp_path / name, {f"x/{name}": BARE_PAGE})
        assert locate("https://x.example/x", detection=NEXT, root=root).path == \
            f"app/x/{name}"


def test_a_low_confidence_detection_caps_the_locator_at_none(tmp_path):
    root = app(tmp_path, {"pricing/page.tsx": METADATA_PAGE})
    mixed = Detection("next-app-router", "low",
                      ("next.config.mjs", "app/layout.tsx", "pages/_app.tsx"))
    found = locate("https://x.example/pricing", detection=mixed, root=root)
    assert found.path == "app/pricing/page.tsx"
    assert found.confidence == "none"


def test_a_medium_confidence_detection_caps_the_locator_at_inferred(tmp_path):
    root = app(tmp_path, {"pricing/page.tsx": METADATA_PAGE})
    guessy = Detection("next-app-router", "medium", ("app/layout.tsx",))
    assert locate("https://x.example/pricing", detection=guessy,
                  root=root).confidence == "inferred"


def test_an_unimplemented_framework_is_honestly_not_located(tmp_path):
    for name in ("next-pages-router", "astro", "nuxt", "sveltekit", "eleventy",
                 "wordpress", "unknown"):
        detection = Detection(name, "high", ("marker",))
        assert locate("https://x.example/", detection=detection,
                      root=tmp_path) == NOT_LOCATED


def test_no_app_directory_is_not_located(tmp_path):
    (tmp_path / "next.config.mjs").write_text("")
    assert locate("https://x.example/", detection=NEXT, root=tmp_path) == NOT_LOCATED


def test_not_located_is_the_default_location():
    assert NOT_LOCATED == Location()
    assert NOT_LOCATED.path is None
    assert NOT_LOCATED.line is None
    assert NOT_LOCATED.confidence == "none"


from omnirank.locator import blast_radius   # noqa: E402  (grouped with the suite above)

STATIC = Detection("static", "medium", ("index.html",))
JEKYLL = Detection("jekyll", "high", ("_config.yml", "_layouts"))
HUGO = Detection("hugo", "high", ("hugo.toml",))

PAGE_HTML = """<!doctype html>
<html lang="en">
  <head>
    <title>Home</title>
  </head>
  <body><h1>Home</h1></body>
</html>
"""


def files(tmp_path: Path, tree: dict[str, str]) -> Path:
    for relative, body in tree.items():
        path = tmp_path / relative
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(body)
    return tmp_path


def test_static_root_resolves_to_index_html(tmp_path):
    root = files(tmp_path, {"index.html": PAGE_HTML})
    found = locate("https://x.example/", detection=STATIC, root=root)
    assert found.path == "index.html"
    assert found.confidence == "inferred", "medium detection caps at inferred"
    assert found.line == 3, "the <head> line"


def test_static_nested_directory_index(tmp_path):
    root = files(tmp_path, {"pricing/index.html": PAGE_HTML})
    assert locate("https://x.example/pricing", detection=STATIC,
                  root=root).path == "pricing/index.html"


def test_static_flat_html_file(tmp_path):
    root = files(tmp_path, {"pricing.html": PAGE_HTML})
    assert locate("https://x.example/pricing/", detection=STATIC,
                  root=root).path == "pricing.html"


def test_static_inside_a_build_directory(tmp_path):
    root = files(tmp_path, {"public/about/index.html": PAGE_HTML})
    assert locate("https://x.example/about", detection=STATIC,
                  root=root).path == "public/about/index.html"


def test_two_static_candidates_are_an_ambiguity_not_a_choice(tmp_path):
    root = files(tmp_path, {"pricing.html": PAGE_HTML,
                            "pricing/index.html": PAGE_HTML})
    assert locate("https://x.example/pricing", detection=STATIC,
                  root=root) == NOT_LOCATED


def test_static_with_no_candidate_is_not_located(tmp_path):
    root = files(tmp_path, {"index.html": PAGE_HTML})
    assert locate("https://x.example/nowhere", detection=STATIC,
                  root=root) == NOT_LOCATED


def test_jekyll_resolves_to_the_source_page_not_the_built_site(tmp_path):
    root = files(tmp_path, {"pricing.md": "---\nlayout: page\n---\n# Pricing\n",
                            "_site/pricing/index.html": PAGE_HTML})
    found = locate("https://x.example/pricing", detection=JEKYLL, root=root)
    assert found.path == "pricing.md"
    assert found.line is None, "Markdown has no <head>"
    assert found.confidence == "exact"


def test_jekyll_root(tmp_path):
    root = files(tmp_path, {"index.html": PAGE_HTML})
    found = locate("https://x.example/", detection=JEKYLL, root=root)
    assert found.path == "index.html"
    assert found.line == 3


def test_hugo_resolves_into_content(tmp_path):
    root = files(tmp_path, {"content/pricing.md": "---\ntitle: Pricing\n---\n"})
    assert locate("https://x.example/pricing", detection=HUGO,
                  root=root).path == "content/pricing.md"


def test_hugo_root_is_the_index_bundle(tmp_path):
    root = files(tmp_path, {"content/_index.md": "---\ntitle: Home\n---\n"})
    assert locate("https://x.example/", detection=HUGO,
                  root=root).path == "content/_index.md"


def test_hugo_page_bundle(tmp_path):
    root = files(tmp_path, {"content/pricing/index.md": "---\ntitle: P\n---\n"})
    assert locate("https://x.example/pricing", detection=HUGO,
                  root=root).path == "content/pricing/index.md"


# -- containment: the convention resolvers must never escape `root` ---------
#
# `root` lives one level inside `tmp_path` for every case below, so an
# "outside" marker planted directly in `tmp_path` sits one directory above
# the project root -- exactly the shape of the adversarial reproduction.

def test_static_url_traversal_cannot_escape_root(tmp_path):
    root = files(tmp_path / "site", {"index.html": PAGE_HTML})
    (tmp_path / "OUTSIDE_MARKER.html").write_text(PAGE_HTML)
    assert locate("https://x.example/../OUTSIDE_MARKER", detection=STATIC,
                  root=root) == NOT_LOCATED


def test_jekyll_url_traversal_cannot_escape_root(tmp_path):
    root = files(tmp_path / "site", {"index.html": PAGE_HTML})
    (tmp_path / "OUTSIDE_MARKER.md").write_text("# outside\n")
    assert locate("https://x.example/../OUTSIDE_MARKER", detection=JEKYLL,
                  root=root) == NOT_LOCATED


def test_hugo_url_traversal_cannot_escape_root(tmp_path):
    root = files(tmp_path / "site", {"content/_index.md": "---\ntitle: Home\n---\n"})
    (tmp_path / "OUTSIDE_MARKER.md").write_text("---\ntitle: Outside\n---\n")
    assert locate("https://x.example/../OUTSIDE_MARKER", detection=HUGO,
                  root=root) == NOT_LOCATED


def test_a_bare_path_without_a_scheme_cannot_traverse_either(tmp_path):
    # `locate()` is documented to accept a URL, but `route_of` never requires
    # a scheme -- a bare path must be just as contained as a full URL.
    root = files(tmp_path / "site", {"index.html": PAGE_HTML})
    (tmp_path / "OUTSIDE_MARKER.html").write_text(PAGE_HTML)
    assert locate("../OUTSIDE_MARKER", detection=STATIC, root=root) == NOT_LOCATED


def test_a_symlink_inside_the_repo_pointing_outside_it_is_rejected(tmp_path):
    root = tmp_path / "site"
    root.mkdir()
    outside = tmp_path / "OUTSIDE_MARKER.html"
    outside.write_text(PAGE_HTML)
    (root / "pricing.html").symlink_to(outside)
    assert locate("https://x.example/pricing", detection=STATIC,
                  root=root) == NOT_LOCATED


def test_normal_convention_resolution_still_works_after_the_containment_guard(tmp_path):
    static_root = files(tmp_path / "static-site", {"pricing/index.html": PAGE_HTML})
    assert locate("https://x.example/pricing", detection=STATIC,
                  root=static_root).path == "pricing/index.html"

    jekyll_root = files(tmp_path / "jekyll-site",
                        {"pricing.md": "---\nlayout: page\n---\n# Pricing\n"})
    assert locate("https://x.example/pricing", detection=JEKYLL,
                  root=jekyll_root).path == "pricing.md"

    hugo_root = files(tmp_path / "hugo-site", {"content/pricing.md": "---\ntitle: P\n---\n"})
    assert locate("https://x.example/pricing", detection=HUGO,
                  root=hugo_root).path == "content/pricing.md"


def test_every_located_result_stays_inside_root(tmp_path):
    # Property-style guard, not tied to one resolver: whatever a resolver
    # returns, `root / result.path` must resolve to a descendant of `root`.
    # This is meant to also catch a *future* resolver that reintroduces the
    # hole, not just the three fixed here.
    cases = [
        (STATIC, files(tmp_path / "s1", {"index.html": PAGE_HTML}), "/"),
        (STATIC, files(tmp_path / "s2", {"pricing/index.html": PAGE_HTML}), "/pricing"),
        (JEKYLL, files(tmp_path / "j1", {"pricing.md": "---\n---\n"}), "/pricing"),
        (HUGO, files(tmp_path / "h1", {"content/pricing.md": "---\n---\n"}), "/pricing"),
        (NEXT, app(tmp_path / "n1", {"pricing/page.tsx": METADATA_PAGE}), "/pricing"),
    ]
    checked = 0
    for detection, root, route in cases:
        found = locate(f"https://x.example{route}", detection=detection, root=root)
        assert found.path is not None, f"expected a location for {route!r}"
        assert (root / found.path).resolve().is_relative_to(root.resolve())
        checked += 1
    assert checked == len(cases)


def test_static_resolution_is_case_sensitive(tmp_path):
    # `.is_file()` alone follows the host filesystem's own case folding: on
    # by default on macOS and Windows, off on Linux CI. `next-app-router`
    # does plain string comparison and is case-sensitive everywhere; the
    # convention resolvers must match that rather than pass locally and fail
    # in CI (or vice versa).
    root = files(tmp_path, {"Pricing.html": PAGE_HTML})
    assert locate("https://x.example/pricing", detection=STATIC, root=root) == NOT_LOCATED


def test_blast_radius_is_one_for_a_single_page_file(tmp_path):
    root = files(tmp_path, {"index.html": PAGE_HTML})
    found = locate("https://x.example/", detection=STATIC, root=root)
    assert blast_radius(found, detection=STATIC, root=root) == 1


def test_blast_radius_is_one_for_a_static_next_route(tmp_path):
    root = app(tmp_path, {"pricing/page.tsx": METADATA_PAGE})
    found = locate("https://x.example/pricing", detection=NEXT, root=root)
    assert blast_radius(found, detection=NEXT, root=root) == 1


def test_blast_radius_is_unknown_for_a_dynamic_next_route(tmp_path):
    # A [slug] page serves an unknown number of routes. "Unknown" must never be
    # optimistically read as "one" -- that is how a literal canonical lands in a
    # file serving 10,000 routes.
    root = app(tmp_path, {"blog/[slug]/page.tsx": METADATA_PAGE})
    found = locate("https://x.example/blog/hello", detection=NEXT, root=root)
    assert blast_radius(found, detection=NEXT, root=root) is None


def test_blast_radius_is_unknown_for_an_unlocated_finding(tmp_path):
    assert blast_radius(NOT_LOCATED, detection=NEXT, root=tmp_path) is None


def test_blast_radius_is_unknown_for_an_unimplemented_framework(tmp_path):
    astro = Detection("astro", "high", ("astro.config.mjs",))
    located = Location(path="src/pages/index.astro", line=None, confidence="exact")
    assert blast_radius(located, detection=astro, root=tmp_path) is None
