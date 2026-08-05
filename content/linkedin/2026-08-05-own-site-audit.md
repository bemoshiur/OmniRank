I ran our own website through a tool I'd been building. 57 pages.

Not one of them had an answer an AI could quote.

---

Here's the problem I keep running into in business development.

A prospect used to find us by searching, landing on a page, and reading it. Increasingly they don't. They ask ChatGPT, Perplexity or Gemini "who does data engineering in Bangladesh" — and they read whatever those engines say back.

If your page has no clean, liftable answer near the top, the engine has nothing to quote. You are not ranked low. You are absent from the conversation.

And here's the part that makes it hard to catch: you can't see it in your analytics. Most AI referrals arrive with no referrer at all, so they land in "Direct". Whatever number you're looking at is a floor, not a measure.

---

So I built something to measure it, and pointed it at ticonsys.com first.

  57 pages audited
  Answer-engine readiness: 33/100
  57 pages with no h1
  57 pages with no canonical URL
  57 pages with nothing an AI could lift and cite

Not a great look for the guy writing this post. But you can't fix what you refuse to measure, and I'd rather find it than have a prospect's ChatGPT session find it for me.

---

The tool is open source. MIT licensed, no signup, runs on your machine:

github.com/bemoshiur/OmniRank

  pip install, point it at any URL, get a scored report

It checks three things at once, because search crawlers, answer engines and generative engines all read the same HTML: classic SEO, answer-engine readiness, and whether AI crawlers can actually ingest your site as a source.

It also does something the commercial tools structurally cannot — it runs inside your repository, so it tells you *which file* is wrong, not just which URL.

---

If you run it on your own site, I'd genuinely like to know what it found — especially if it flagged something that turned out to be wrong. Precision is the whole point, and I'd rather hear about a false positive than not.

What's your site scoring?

#SEO #AEO #GEO #AISearch #BusinessDevelopment #OpenSource #Bangladesh
