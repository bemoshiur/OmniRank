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


def test_parallel_slots_and_private_folders_are_not_route_segments(tmp_path):
    root = app(tmp_path, {"@modal/settings/page.tsx": METADATA_PAGE,
                          "_components/page.tsx": BARE_PAGE})
    found = locate("https://x.example/settings", detection=NEXT, root=root)
    assert found.path == "app/@modal/settings/page.tsx"


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
