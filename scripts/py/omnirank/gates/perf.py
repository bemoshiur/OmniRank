from __future__ import annotations

from ..page import PageData
from ..report import Finding

RESPONSE_WARN_MS = 2000
RESPONSE_ERROR_MS = 5000
HTML_WARN_BYTES = 500_000
MAX_HEAD_SCRIPTS = 2

# gzip and deflate are the only encodings OmniRank's own client (see fetch.py) ever
# advertises in Accept-Encoding, so they are the only ones it can actually observe
# a server choosing. br/zstd are matched defensively in case a server ignores
# Accept-Encoding and sends one anyway (fetch() already handles that response
# gracefully), but OmniRank never claims to verify them — see docs/audit-guide.md.
_COMPRESSED = ("gzip", "br", "deflate", "zstd")


def _f(id_: str, gate: str, url: str, severity: str, observed: str,
       expected: str, fix: str) -> Finding:
    return Finding(id=id_, severity=severity, layer="perf", url=url, gate=gate,
                   observed=observed, expected=expected, fix=fix)


def _response_time(page: PageData) -> list[Finding]:
    """Wall-clock time for OmniRank's own request, start to finish.

    This is NOT time-to-first-byte: `page.elapsed_ms` brackets the entire
    `client.get()` call — DNS, TCP, TLS, request, and reading the *complete* response
    body — not the time until the first byte arrived. Measuring it as TTFB overstates
    the real figure severalfold on anything but a tiny page, and produces false
    positives that vanish on re-measurement. This is a smoke signal derived from a
    full download, not a user-experienced metric and not real TTFB; the finding text
    says so.
    """
    if page.elapsed_ms >= RESPONSE_ERROR_MS:
        return [_f("perf.response-time.critical", "response-time", page.url, "error",
                   f"{page.elapsed_ms} ms for the full response to this audit's request",
                   f"under {RESPONSE_WARN_MS} ms",
                   "Investigate server response time: cold starts, uncached database "
                   "queries, or origin distance. This measures the complete download, "
                   "not server think-time, and is measured from where this audit ran, "
                   "so treat it as a signal to investigate rather than a user metric.")]
    if page.elapsed_ms >= RESPONSE_WARN_MS:
        return [_f("perf.response-time.slow", "response-time", page.url, "warning",
                   f"{page.elapsed_ms} ms for the full response to this audit's request",
                   f"under {RESPONSE_WARN_MS} ms",
                   "Consider caching or a CDN. This measures the complete download, "
                   "not server think-time, and is measured from where this audit ran, "
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
        *_response_time(page),
        *_page_weight(page),
        *_compression(page),
        *_render_blocking(page),
    ]
