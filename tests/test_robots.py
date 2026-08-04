
from omnirank import robots

SIMPLE = "User-agent: *\nDisallow: /private/\n"
WILDCARD = "User-agent: *\nDisallow: /*.pdf$\n"
OVERLAPPING = "User-agent: *\nDisallow: /docs/\nAllow: /docs/public/\n"
DISJOINT = "User-agent: *\nDisallow: /admin/\nAllow: /blog/\n"


def test_a_file_with_no_wildcards_or_allows_is_always_evaluated():
    verdict = robots.disallowed_urls(SIMPLE, ["https://x.example/private/a",
                                              "https://x.example/open"])
    assert verdict.evaluated is True
    assert verdict.reason is None
    assert verdict.disallowed == ("https://x.example/private/a",)


def test_rules_need_wildcards_detects_star_and_dollar():
    assert robots.rules_need_wildcards(WILDCARD) is True
    assert robots.rules_need_wildcards("User-agent: *\nDisallow: /a/*/b\n") is True
    assert robots.rules_need_wildcards(SIMPLE) is False
    assert robots.rules_need_wildcards(OVERLAPPING) is False, (
        "the * on the User-agent line is a group selector, not a path wildcard")


def test_rules_need_longest_match_only_when_an_allow_and_a_disallow_overlap():
    assert robots.rules_need_longest_match(OVERLAPPING) is True
    assert robots.rules_need_longest_match("User-agent: *\nAllow: /\nDisallow: /a/\n") is True
    assert robots.rules_need_longest_match(DISJOINT) is False, (
        "non-overlapping paths give the same answer under either matcher")
    assert robots.rules_need_longest_match(SIMPLE) is False


def test_rules_need_longest_match_does_not_cross_group_boundaries():
    text = ("User-agent: Googlebot\nDisallow: /docs/\n"
            "User-agent: Bingbot\nAllow: /docs/public/\n")
    assert robots.rules_need_longest_match(text) is False, (
        "rules in different user-agent groups never compete with one another")


def test_comments_and_blank_lines_are_ignored():
    text = "# hello\n\nUser-agent: *\nDisallow: /p/   # trailing\n"
    verdict = robots.disallowed_urls(text, ["https://x.example/p/a"])
    assert verdict.evaluated is True
    assert verdict.disallowed == ("https://x.example/p/a",)


def test_a_wildcard_file_is_refused_when_the_interpreter_cannot_match_it():
    verdict = robots.disallowed_urls(WILDCARD, ["https://x.example/a/b.pdf"])
    if robots.matcher_supports_wildcards():
        assert verdict.evaluated is True
        assert verdict.disallowed == ("https://x.example/a/b.pdf",)
    else:
        assert verdict.evaluated is False
        assert verdict.reason == robots.UNSUPPORTED_WILDCARDS
        assert verdict.disallowed == (), (
            "a refused verdict must carry no judgement at all")


def test_an_overlapping_file_is_refused_when_the_interpreter_is_order_dependent():
    verdict = robots.disallowed_urls(OVERLAPPING, ["https://x.example/docs/public/x"])
    if robots.matcher_supports_longest_match():
        assert verdict.evaluated is True
        assert verdict.disallowed == (), "longest-match: Allow wins over the shorter Disallow"
    else:
        assert verdict.evaluated is False
        assert verdict.reason == robots.UNSUPPORTED_LONGEST_MATCH


def test_the_capability_probes_agree_with_the_matcher_they_probe():
    """The probes must match OBSERVED matcher behaviour, never a version number.

    The intent here is to catch a probe that has silently started returning a
    constant. An earlier version cross-checked against `sys.version_info >= (3, 14)`,
    reasoning that both capabilities arrived in CPython's 3.14 RFC 9309 rewrite.
    That was wrong, and CI caught it: the change was BACKPORTED, so 3.13.7 reports no
    wildcard support while 3.13.14 reports it. Any version inference calls one of
    those wrong — which is precisely the failure the probe exists to prevent, so
    asserting one here would have hard-coded the bug into its own regression test.

    Observing the matcher directly keeps the original intent (a stuck constant still
    fails, because these two witnesses are computed independently of the probe) and
    is immune to whatever CPython backports next.
    """
    import urllib.robotparser

    def matcher_observes_wildcards() -> bool:
        parser = urllib.robotparser.RobotFileParser()
        parser.parse(["User-agent: *", "Disallow: /*.pdf$"])
        return not parser.can_fetch("*", "/a/b.pdf")

    def matcher_observes_longest_match() -> bool:
        parser = urllib.robotparser.RobotFileParser()
        parser.parse(["User-agent: *", "Disallow: /docs/", "Allow: /docs/public/"])
        return parser.can_fetch("*", "/docs/public/x")

    assert robots.matcher_supports_wildcards() is matcher_observes_wildcards()
    assert robots.matcher_supports_longest_match() is matcher_observes_longest_match()


def test_a_googlebot_group_overrides_the_wildcard_group():
    text = "User-agent: *\nDisallow: /\nUser-agent: Googlebot\nDisallow:\n"
    verdict = robots.disallowed_urls(text, ["https://x.example/a"])
    assert verdict.evaluated is True
    assert verdict.disallowed == ()


def test_the_wildcard_group_applies_when_there_is_no_agent_specific_group():
    verdict = robots.disallowed_urls("User-agent: *\nDisallow: /admin/\n",
                                     ["https://x.example/admin/x"])
    assert verdict.disallowed == ("https://x.example/admin/x",)


def test_an_empty_robots_file_disallows_nothing():
    verdict = robots.disallowed_urls("", ["https://x.example/a"])
    assert verdict.evaluated is True
    assert verdict.disallowed == ()
