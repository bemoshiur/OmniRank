"""Detect a project's routing convention from files on disk.

Detection MUST be able to return `unknown`. A bespoke project is the common
case, and a confident wrong answer here is worse than an admitted absence:
`unknown` produces a locator confidence of `none`, which demotes every fix on
that repo to display-only, which is exactly right. A wrong guess instead
produces a confident diff against the wrong file.

Confidence is reported, never hidden, and it propagates: locator.py caps its own
confidence at DETECTION_CEILING[confidence], and applicability.py caps the fix
at that. A `low`-confidence detection can therefore only ever produce
display-only fixes.

Ordering matters and is deliberate: a framework marker always beats a generic
one, so a stray `index.html` in an Astro project does not make it `static`.
"""
from __future__ import annotations

from collections.abc import Iterable
from dataclasses import dataclass
from pathlib import Path
from typing import Literal

Framework = Literal[
    "next-app-router", "next-pages-router", "astro", "nuxt", "sveltekit",
    "hugo", "jekyll", "eleventy", "wordpress", "static", "unknown",
]

DetectionConfidence = Literal["high", "medium", "low", "none"]

# `stack.framework` in omnirank.config.schema.json uses a slightly different
# vocabulary: it predates this module, spells the Next pages router
# `next-pages`, and carries `shopify` and `other`, neither of which this module
# can locate against. Anything with no routing convention we implement maps to
# `unknown`, which is honest -- it is exactly what the locator can do with it.
CONFIG_FRAMEWORK_ALIASES: dict[str, Framework] = {
    "next-app-router": "next-app-router",
    "next-pages": "next-pages-router",
    "next-pages-router": "next-pages-router",
    "astro": "astro",
    "nuxt": "nuxt",
    "sveltekit": "sveltekit",
    "hugo": "hugo",
    "jekyll": "jekyll",
    "eleventy": "eleventy",
    "wordpress": "wordpress",
    "static": "static",
    "shopify": "unknown",
    "other": "unknown",
}


@dataclass(frozen=True)
class Detection:
    """What was detected, how sure we are, and the files that decided it.

    `evidence` holds repo-relative POSIX paths (plus, occasionally, a short
    explanatory string when the deciding fact is an ABSENCE). It exists so
    `omnirank fix` can print why it believes what it believes -- a detector that
    cannot show its work is indistinguishable from a guess.

    INVARIANT: framework == "unknown" implies confidence == "none".
    """

    framework: Framework
    confidence: DetectionConfidence
    evidence: tuple[str, ...]


UNKNOWN = Detection(framework="unknown", confidence="none",
                    evidence=("no framework marker found",))

_NEXT_CONFIGS = ("next.config.js", "next.config.mjs", "next.config.ts",
                 "next.config.cjs")
_ASTRO_CONFIGS = ("astro.config.mjs", "astro.config.js", "astro.config.ts",
                  "astro.config.mts", "astro.config.cjs")
_NUXT_CONFIGS = ("nuxt.config.ts", "nuxt.config.js", "nuxt.config.mjs")
_ELEVENTY_CONFIGS = (".eleventy.js", "eleventy.config.js", "eleventy.config.mjs",
                     "eleventy.config.cjs")
_HUGO_CONFIGS = ("hugo.toml", "hugo.yaml", "hugo.json")
_LAYOUT_FILES = ("layout.tsx", "layout.jsx", "layout.ts", "layout.js")
_APP_FILES = ("_app.tsx", "_app.jsx", "_app.ts", "_app.js")
_STATIC_ROOTS = ("", "public", "dist")


def _first_file(root: Path, names: Iterable[str]) -> str | None:
    for name in names:
        if (root / name).is_file():
            return name
    return None


def _first_file_in(root: Path, dirs: Iterable[str],
                   names: Iterable[str]) -> str | None:
    """The first `<dir>/<name>` that exists, as a repo-relative POSIX path."""
    for directory in dirs:
        for name in names:
            if (root / directory / name).is_file():
                return f"{directory}/{name}"
    return None


def _wordpress(root: Path) -> Detection | None:
    if (root / "wp-config.php").is_file():
        return Detection("wordpress", "high", ("wp-config.php",))
    return None


def _next(root: Path) -> Detection | None:
    config = _first_file(root, _NEXT_CONFIGS)
    app = _first_file_in(root, ("app", "src/app"), _LAYOUT_FILES)
    pages = _first_file_in(root, ("pages", "src/pages"), _APP_FILES)
    if config is None and app is None and pages is None:
        return None

    evidence = tuple(item for item in (config, app, pages) if item is not None)
    if app is not None and pages is not None:
        # Next resolves a mixed-router project per route. This release cannot,
        # and `low` is how it says so: locator.py turns `low` into confidence
        # `none`, so every fix here is display-only rather than a coin flip.
        return Detection("next-app-router", "low", evidence)
    if app is not None:
        return Detection("next-app-router", "high" if config else "medium", evidence)
    if pages is not None:
        return Detection("next-pages-router", "high" if config else "medium", evidence)
    # A next.config.* with neither router directory: certainly Next, but we
    # cannot say which router owns the head, and `unknown` never carries
    # confidence.
    return Detection("unknown", "none",
                     (*evidence, "no app/ or pages/ router directory"))


def _astro(root: Path) -> Detection | None:
    config = _first_file(root, _ASTRO_CONFIGS)
    return Detection("astro", "high", (config,)) if config else None


def _nuxt(root: Path) -> Detection | None:
    config = _first_file(root, _NUXT_CONFIGS)
    return Detection("nuxt", "high", (config,)) if config else None


def _sveltekit(root: Path) -> Detection | None:
    if not (root / "svelte.config.js").is_file():
        return None
    if (root / "src" / "routes").is_dir():
        return Detection("sveltekit", "high", ("svelte.config.js", "src/routes"))
    return Detection("sveltekit", "medium", ("svelte.config.js",))


def _hugo(root: Path) -> Detection | None:
    config = _first_file(root, _HUGO_CONFIGS)
    if config:
        return Detection("hugo", "high", (config,))
    # `config.toml` alone is far too generic to decide on -- Rust, Netlify and
    # a dozen other tools use that filename -- so it needs Hugo's own directory
    # shape alongside it.
    if ((root / "config.toml").is_file() and (root / "content").is_dir()
            and (root / "layouts").is_dir()):
        return Detection("hugo", "medium", ("config.toml", "content", "layouts"))
    return None


def _jekyll(root: Path) -> Detection | None:
    if not (root / "_config.yml").is_file():
        return None
    if (root / "_layouts").is_dir():
        return Detection("jekyll", "high", ("_config.yml", "_layouts"))
    return Detection("jekyll", "medium", ("_config.yml",))


def _eleventy(root: Path) -> Detection | None:
    config = _first_file(root, _ELEVENTY_CONFIGS)
    return Detection("eleventy", "high", (config,)) if config else None


def _static(root: Path) -> Detection | None:
    """`static` is the last detector tried (see `_DETECTORS` below): by the
    time this runs, every framework-specific marker has already failed to
    match, so an `index.html` at the repo root or a conventional build output
    is as strong a signal as this module can get for "plain HTML, no
    framework" -- `high`, the same confidence a single named config file
    earns every other framework here (`astro.config.mjs`, `hugo.toml`, a
    `wp-config.php`).

    This was `medium` through v0.3.0, which -- via DETECTION_CEILING in
    locator.py -- capped every static-site locate() at `inferred`, and
    CONFIDENCE_CEILING caps `inferred` at `unsafe`. A bare static site,
    the plain-HTML case users try first, could therefore NEVER reach
    `applicability == "safe"` and `omnirank fix` could never emit a diff for
    it, despite `_locate_static` and `canonical.missing` being fully
    implemented and tested. Raising this to `high` does not weaken the
    genuine ambiguity guard: `_locate_by_convention` in locator.py already
    returns NOT_LOCATED (confidence `none`) whenever more than one on-disk
    file could serve the SAME route (e.g. both `pricing.html` and
    `pricing/index.html` exist) -- a per-route check that is completely
    independent of this per-repo detection confidence and is unaffected by
    it either way. The two axes stay orthogonal on purpose: this confidence
    says "how sure are we this project has no framework", not "how sure are
    we about any one route", which is what the locator's own guard is for.
    """
    for base in _STATIC_ROOTS:
        relative = f"{base}/index.html" if base else "index.html"
        if (root / relative).is_file():
            return Detection("static", "high", (relative,))
    return None


# Order is load-bearing: every framework-specific marker is checked before the
# generic index.html sweep, so a build output inside a framework project never
# reclassifies it as `static`.
_DETECTORS = (_wordpress, _next, _astro, _nuxt, _sveltekit, _hugo, _jekyll,
              _eleventy, _static)


def detect(root: str | Path) -> Detection:
    """The routing convention `root` uses, or UNKNOWN. Never raises."""
    base = Path(root)
    for detector in _DETECTORS:
        found = detector(base)
        if found is not None:
            return found
    return UNKNOWN
