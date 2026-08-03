from omnirank.gates import perf
from omnirank.page import PageData

URL = "https://x.example/"

FAST_HEAD = "<head><title>T</title></head>"


def page(html: str = f"<html>{FAST_HEAD}<body><h1>H</h1></body></html>",
         elapsed_ms: int = 120, headers: dict | None = None) -> PageData:
    return PageData(url=URL, html=html, status=200, elapsed_ms=elapsed_ms,
                    headers=headers if headers is not None
                    else {"content-encoding": "gzip"})


def ids(findings) -> set[str]:
    return {f.id for f in findings}


def test_a_fast_small_compressed_page_is_clean():
    assert perf.run(page()) == []


def test_every_finding_carries_the_perf_layer():
    slow = page(elapsed_ms=3000, headers={})
    assert all(f.layer == "perf" for f in perf.run(slow))


def test_slow_response_is_a_warning():
    found = [f for f in perf.run(page(elapsed_ms=2500))
             if f.id == "perf.response-time.slow"]
    assert found and found[0].severity == "warning"
    assert found[0].gate == "response-time"
    assert "2500" in found[0].observed


def test_very_slow_response_is_an_error_not_two_findings():
    findings = perf.run(page(elapsed_ms=6000))
    assert "perf.response-time.critical" in ids(findings)
    assert "perf.response-time.slow" not in ids(findings), "escalate, do not double-report"
    critical = [f for f in findings if f.id == "perf.response-time.critical"][0]
    assert critical.severity == "error"


def test_response_time_finding_does_not_claim_to_be_ttfb_or_a_field_metric():
    found = [f for f in perf.run(page(elapsed_ms=2500)) if f.gate == "response-time"][0]
    combined = (found.fix + found.observed).lower()
    assert "lighthouse" not in combined
    assert "core web vitals" not in combined
    assert "first byte" not in combined, (
        "elapsed_ms brackets the full response read, not first byte — the finding "
        "text must not claim otherwise")


def test_response_time_below_the_new_higher_thresholds_is_clean():
    # Old TTFB-labelled thresholds (800ms/2500ms) would have flagged this; the
    # renamed gate measures a full download, so its thresholds are higher.
    assert perf.run(page(elapsed_ms=1500)) == []


def test_heavy_html_is_a_warning():
    big = "<html><head><title>T</title></head><body>" + ("x" * 600_000) + "</body></html>"
    found = [f for f in perf.run(page(html=big)) if f.id == "perf.page-weight.heavy"]
    assert found and found[0].gate == "page-weight"


def test_page_weight_reports_bytes_and_kib_consistently():
    # S9: at exactly 500,001 bytes the old code printed "488 KB of HTML ...
    # expected under 488 KB" -- self-contradictory (the page is over the limit but
    # both figures floor to the same truncated number) and mislabelled (KB, not
    # KiB, despite dividing by 1024).
    html = "x" * 500_001
    assert len(html.encode("utf-8")) == 500_001
    found = [f for f in perf.run(page(html=html)) if f.id == "perf.page-weight.heavy"][0]
    assert found.observed == "500001 bytes (489 KiB) of HTML before any subresource"
    assert found.expected == "under 500000 bytes (488 KiB)"


def test_missing_compression_is_a_warning():
    found = [f for f in perf.run(page(headers={})) if f.id == "perf.compression.missing"]
    assert found and found[0].gate == "compression"


def test_brotli_counts_as_compressed():
    assert "perf.compression.missing" not in ids(
        perf.run(page(headers={"content-encoding": "br"})))


def test_render_blocking_head_scripts_are_flagged():
    head = ("<head><title>T</title>"
            "<script src='/a.js'></script>"
            "<script src='/b.js'></script>"
            "<script src='/c.js'></script></head>")
    found = [f for f in perf.run(page(html=f"<html>{head}<body></body></html>"))
             if f.id == "perf.render-blocking.head-scripts"]
    assert found and "3" in found[0].observed


def test_async_and_defer_scripts_are_not_render_blocking():
    head = ("<head><title>T</title>"
            "<script src='/a.js' async></script>"
            "<script src='/b.js' defer></script>"
            "<script src='/c.js' defer></script></head>")
    assert "perf.render-blocking.head-scripts" not in ids(
        perf.run(page(html=f"<html>{head}<body></body></html>")))


def test_inline_scripts_do_not_count_as_render_blocking():
    head = ("<head><title>T</title>"
            "<script>var a=1</script><script>var b=2</script>"
            "<script>var c=3</script></head>")
    assert "perf.render-blocking.head-scripts" not in ids(
        perf.run(page(html=f"<html>{head}<body></body></html>"))), (
        "an inline script has no network cost; the gate is about blocking fetches")


def test_body_scripts_are_not_flagged():
    html = ("<html><head><title>T</title></head><body>"
            "<script src='/a.js'></script><script src='/b.js'></script>"
            "<script src='/c.js'></script></body></html>")
    assert "perf.render-blocking.head-scripts" not in ids(perf.run(page(html=html)))
