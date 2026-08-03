from __future__ import annotations

from dataclasses import dataclass, field

from bs4 import BeautifulSoup

from .fetch import Fetched


@dataclass(frozen=True)
class PageData:
    """A fetched page kept alive for the site-level pass.

    The per-URL gates are stateless and throw their HTML away. Cross-URL findings
    — duplicate titles, canonical chains, hreflang reciprocity — need the whole
    collection at once, so audit_site keeps one of these per reachable URL.
    """

    url: str
    html: str
    status: int
    elapsed_ms: int
    headers: dict[str, str]
    _soup: list = field(default_factory=list, repr=False, compare=False)

    @classmethod
    def from_fetched(cls, f: Fetched) -> PageData:
        return cls(url=f.url, html=f.text, status=f.status,
                   elapsed_ms=f.elapsed_ms, headers=dict(f.headers))

    def soup(self) -> BeautifulSoup:
        """Parsed HTML, memoised. The site pass must not re-parse every page."""
        if not self._soup:
            self._soup.append(BeautifulSoup(self.html, "lxml"))
        return self._soup[0]

    @property
    def lang(self) -> str | None:
        """The <html lang> value, or None. Drives AnswerBlock band selection."""
        tag = self.soup().find("html")
        value = tag.get("lang") if tag else None
        return value.strip() if value else None
