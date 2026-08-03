from __future__ import annotations

import warnings

from bs4 import XMLParsedAsHTMLWarning

# OmniRank fetches sitemap and sitemap-index XML directly, and any audited target
# can itself be an XML document. BeautifulSoup always parses with the HTML parser
# (page.py hard-codes "lxml"), which is correct for HTML but prints this warning
# on every XML document — roughly 50 lines of noise per URL. Silenced once, here,
# rather than at every call site.
warnings.filterwarnings("ignore", category=XMLParsedAsHTMLWarning)

__version__ = "0.2.0"
