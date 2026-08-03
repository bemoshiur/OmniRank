from __future__ import annotations

from ..page import PageData
from ..report import Finding

TTFB_WARN_MS = 800
TTFB_ERROR_MS = 2500
HTML_WARN_BYTES = 500_000
MAX_HEAD_SCRIPTS = 2

_COMPRESSED = ("gzip", "br", "deflate", "zstd")


def _f(id_: str, gate: str, url: str, severity: str, observed: str,
       expected: str, fix: str) -> Finding:
    return Finding(id=id_, severity=severity, layer="perf", url=url, gate=gate,
                   observed=observed, expected=expected, fix=fix)


def _ttfb(page: PageData) -> list[Finding]:
    """Wall-clock time for OmniRank's own request.

    This is a smoke signal, not a user-experienced metric. OmniRank has no browser
    and measures nothing a real visitor experiences; the finding text says so.
    """
    if page.elapsed_ms >= TTFB_ERROR_MS:
        return [_f("perf.ttfb.critical", "ttfb", page.url, "error",
                   f"{page.elapsed_ms} ms to first byte for this audit's request",
                   f"under {TTFB_WARN_MS} ms",
                   "Investigate server response time: cold starts, uncached database "
                   "queries, or origin distance. Measured from where this audit ran, "
                   "so treat it as a signal to investigate rather than a user metric.")]
    if page.elapsed_ms >= TTFB_WARN_MS:
        return [_f("perf.ttfb.slow", "ttfb", page.url, "warning",
                   f"{page.elapsed_ms} ms to first byte for this audit's request",
                   f"under {TTFB_WARN_MS} ms",
                   "Consider caching or a CDN. Measured from where this audit ran, "
                   "so treat it as a signal to investigate rather than a user metric.")]
    return []


def _page_weight(page: PageData) -> list[Finding]:
    size = len(page.html.encode("utf-8"))
    if size <= HTML_WARN_BYTES:
        return []
    return [_f("perf.page-weight.heavy", "page-weight", page.url, "warning",
               f"{size // 1024} KB of HTML before any subresource",
               f"under {HTML_WARN_BYTES // 1024} KB",
               "Large HTML delays parsing and inflates every cache. Look for inlined "
               "data, embedded base64, or a component rendering the whole dataset.")]


def _compression(page: PageData) -> list[Finding]:
    encoding = page.headers.get("content-encoding", "").lower()
    if any(algo in encoding for algo in _COMPRESSED):
        return []
    return [_f("perf.compression.missing", "compression", page.url, "warning",
               "response carried no content-encoding header",
               "gzip, brotli or zstd",
               "Enable compression at the origin or CDN. HTML compresses well and "
               "this is usually a one-line server change.")]


def _render_blocking(page: PageData) -> list[Finding]:
    head = page.soup().find("head")
    if not head:
        return []
    blocking = [s for s in head.find_all("script")
                if s.get("src") and not s.has_attr("async") and not s.has_attr("defer")]
    if len(blocking) <= MAX_HEAD_SCRIPTS:
        return []
    srcs = ", ".join(s.get("src") for s in blocking[:3])
    return [_f("perf.render-blocking.head-scripts", "render-blocking", page.url,
               "warning",
               f"{len(blocking)} render-blocking scripts in <head> ({srcs})",
               f"at most {MAX_HEAD_SCRIPTS}",
               "Add async or defer, or move these below the fold. Each blocks HTML "
               "parsing until it has downloaded and executed.")]


def run(page: PageData) -> list[Finding]:
    """Performance signals derivable from one HTTP response.

    Deliberately excludes anything requiring a browser — no LCP, CLS, INP or
    Lighthouse score. OmniRank does not measure those and must not imply it does.
    """
    return [
        *_ttfb(page),
        *_page_weight(page),
        *_compression(page),
        *_render_blocking(page),
    ]
