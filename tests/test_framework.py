import json
from pathlib import Path

import pytest

from omnirank.framework import (
    CONFIG_FRAMEWORK_ALIASES,
    UNKNOWN,
    Detection,
    detect,
)

ROOT = Path(__file__).resolve().parents[1]


def repo(tmp_path: Path, files: dict[str, str], dirs=()) -> Path:
    for name in dirs:
        (tmp_path / name).mkdir(parents=True, exist_ok=True)
    for name, body in files.items():
        path = tmp_path / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(body)
    return tmp_path


def test_an_empty_directory_is_unknown(tmp_path):
    found = detect(tmp_path)
    assert found == UNKNOWN
    assert found.framework == "unknown"
    assert found.confidence == "none"
    assert found.evidence == ("no framework marker found",)


def test_next_app_router_from_config_plus_app_layout(tmp_path):
    root = repo(tmp_path, {"next.config.mjs": "", "app/layout.tsx": ""})
    found = detect(root)
    assert found.framework == "next-app-router"
    assert found.confidence == "high"
    assert found.evidence == ("next.config.mjs", "app/layout.tsx")


def test_next_app_router_under_src(tmp_path):
    root = repo(tmp_path, {"next.config.js": "", "src/app/layout.jsx": ""})
    found = detect(root)
    assert found.framework == "next-app-router"
    assert found.evidence == ("next.config.js", "src/app/layout.jsx")


def test_next_pages_router_from_config_plus_app_file(tmp_path):
    root = repo(tmp_path, {"next.config.ts": "", "pages/_app.tsx": ""})
    found = detect(root)
    assert found.framework == "next-pages-router"
    assert found.confidence == "high"


def test_a_router_directory_without_next_config_is_only_medium(tmp_path):
    root = repo(tmp_path, {"app/layout.tsx": ""})
    found = detect(root)
    assert found.framework == "next-app-router"
    assert found.confidence == "medium"


def test_both_next_routers_present_drops_to_low_confidence(tmp_path):
    # Next resolves this per route; this release cannot, so it says so instead
    # of picking one silently. Task 5 turns `low` into locator confidence
    # `none`, which makes every fix on this repo display-only.
    root = repo(tmp_path, {"next.config.mjs": "", "app/layout.tsx": "",
                           "pages/_app.tsx": ""})
    found = detect(root)
    assert found.framework == "next-app-router"
    assert found.confidence == "low"
    assert "pages/_app.tsx" in found.evidence


def test_next_config_with_no_router_directory_is_unknown(tmp_path):
    root = repo(tmp_path, {"next.config.mjs": ""})
    found = detect(root)
    assert found.framework == "unknown"
    assert found.confidence == "none"
    assert "next.config.mjs" in found.evidence


def test_astro(tmp_path):
    found = detect(repo(tmp_path, {"astro.config.mjs": ""}))
    assert (found.framework, found.confidence) == ("astro", "high")


def test_nuxt(tmp_path):
    found = detect(repo(tmp_path, {"nuxt.config.ts": ""}))
    assert (found.framework, found.confidence) == ("nuxt", "high")


def test_sveltekit_needs_routes_for_high_confidence(tmp_path):
    bare = detect(repo(tmp_path, {"svelte.config.js": ""}))
    assert (bare.framework, bare.confidence) == ("sveltekit", "medium")


def test_sveltekit_with_routes(tmp_path):
    root = repo(tmp_path, {"svelte.config.js": ""}, dirs=("src/routes",))
    found = detect(root)
    assert (found.framework, found.confidence) == ("sveltekit", "high")


def test_hugo_from_its_named_config(tmp_path):
    found = detect(repo(tmp_path, {"hugo.toml": ""}))
    assert (found.framework, found.confidence) == ("hugo", "high")


def test_hugo_from_legacy_config_toml_needs_corroboration(tmp_path):
    only_config = detect(repo(tmp_path, {"config.toml": ""}))
    assert only_config.framework == "unknown"
    root = repo(tmp_path, {"config.toml": ""}, dirs=("content", "layouts"))
    found = detect(root)
    assert (found.framework, found.confidence) == ("hugo", "medium")


def test_jekyll(tmp_path):
    bare = detect(repo(tmp_path, {"_config.yml": ""}))
    assert (bare.framework, bare.confidence) == ("jekyll", "medium")
    root = repo(tmp_path, {"_config.yml": ""}, dirs=("_layouts",))
    assert detect(root).confidence == "high"


def test_eleventy(tmp_path):
    found = detect(repo(tmp_path, {".eleventy.js": ""}))
    assert (found.framework, found.confidence) == ("eleventy", "high")


def test_wordpress(tmp_path):
    found = detect(repo(tmp_path, {"wp-config.php": "<?php"}))
    assert (found.framework, found.confidence) == ("wordpress", "high")


def test_plain_html_is_static(tmp_path):
    found = detect(repo(tmp_path, {"index.html": "<html></html>"}))
    assert (found.framework, found.confidence) == ("static", "medium")


def test_static_found_in_a_build_directory(tmp_path):
    found = detect(repo(tmp_path, {"public/index.html": "<html></html>"}))
    assert found.framework == "static"
    assert found.evidence == ("public/index.html",)


def test_a_framework_marker_beats_a_stray_index_html(tmp_path):
    root = repo(tmp_path, {"astro.config.mjs": "", "index.html": ""})
    assert detect(root).framework == "astro"


@pytest.mark.parametrize("files", [{}, {"next.config.mjs": ""}, {"README.md": "hi"}])
def test_unknown_always_means_no_confidence(tmp_path, files):
    found = detect(repo(tmp_path, files))
    assert found.framework == "unknown", found
    assert found.confidence == "none", found


def test_detection_is_frozen():
    import dataclasses

    with pytest.raises(dataclasses.FrozenInstanceError):
        UNKNOWN.framework = "astro"


def test_every_config_framework_value_has_an_alias():
    schema = json.loads((ROOT / "schemas" / "omnirank.config.schema.json").read_text())
    declared = set(
        schema["properties"]["stack"]["properties"]["framework"]["enum"])
    missing = sorted(declared - set(CONFIG_FRAMEWORK_ALIASES))
    assert not missing, f"stack.framework values with no alias: {missing}"


def test_config_only_frameworks_alias_to_unknown():
    assert CONFIG_FRAMEWORK_ALIASES["shopify"] == "unknown"
    assert CONFIG_FRAMEWORK_ALIASES["other"] == "unknown"
    assert CONFIG_FRAMEWORK_ALIASES["next-pages"] == "next-pages-router"


def test_detect_accepts_a_string_path(tmp_path):
    repo(tmp_path, {"astro.config.ts": ""})
    assert detect(str(tmp_path)).framework == "astro"


def test_detection_evidence_is_a_tuple_of_repo_relative_paths(tmp_path):
    root = repo(tmp_path, {"next.config.mjs": "", "src/app/layout.ts": ""})
    found = detect(root)
    assert isinstance(found.evidence, tuple)
    assert all(not Path(item).is_absolute() for item in found.evidence)
