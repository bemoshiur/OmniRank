---
name: linkedin-post
description: Draft a daily LinkedIn post for S M Moshiur Rahman about business development, grounded in a real problem he hit that day and real numbers from OmniRank. Use when he says "linkedin post", "today's post", "draft a post", or describes friction he wants written up.
---

# Daily LinkedIn post

Draft one post in Moshiur's voice. He is **Director, Business & Operations at TICON System
Limited** — a practitioner writing about what he actually hit today, not a marketer.

## The one rule

**A post needs a real thing that happened.** If he hasn't given you one, ask for it before
drafting. Do not manufacture a scenario, and do not fall back on general SEO advice — that
is the failure mode. Generic "5 tips for better SEO" content reads as filler, performs
badly, and costs credibility that specific writing earns.

Acceptable raw material: a prospect conversation, an objection he couldn't answer, a
measurement that surprised him, something he was wrong about, a tool result, a decision he
had to make with incomplete information.

## Structure that works

1. **A hook that is a fact, not a claim.** Ideally a number or a short admission.
   "I ran our own website through a tool I built. 57 pages. Not one had an answer an AI
   could quote." Never open with "In today's digital landscape".
2. **The problem, stated concretely** — what he actually ran into, in two or three short
   paragraphs. Short lines. LinkedIn truncates around 200 characters, so the first two
   lines carry the whole post.
3. **Evidence.** Real numbers, indented as a small block. See below for pulling them.
4. **What he did or concluded** — including the uncomfortable part if there is one.
5. **One specific question.** Not "thoughts?" — something a reader can answer in a sentence
   from their own experience.
6. **Link only if it earns its place.** github.com/bemoshiur/OmniRank when relevant.
7. **4–7 hashtags**, lowercase-natural, no keyword stuffing.

Target 1,300–2,000 characters. Longer gets collapsed behind "see more".

## Getting real numbers

Never invent a statistic. When a post would benefit from data, measure it:

```bash
cd "<repo>" && .venv/bin/python -m omnirank.cli audit https://<site> --out /tmp/post.json
```

Then read `/tmp/post.json` for exact per-layer scores and finding counts. Quote what the
tool actually printed. If a number can't be measured, cut the claim rather than soften it.

Research already in the repo that can be cited honestly — with its caveats intact — lives in
`docs/research/`. The brand-mention and AI-citation correlations there are **observational,
mostly English-language B2B, and directional**. Say so if you use them.

## Voice

- First person, past tense, specific.
- Admit the unflattering part. A Director saying his own site scored 33/100 is more
  credible than any polished claim, because nobody fakes that direction.
- No "game-changer", "leverage", "unlock", "in today's world", "the truth is".
- No em-dash-heavy rhetorical flourishes. Plain sentences.
- Never claim a result the work hasn't produced. No client names without permission.

## Angles not yet used

Track these so the daily cadence doesn't repeat itself. Cross one off when used.

- [x] Ran my own company's site through my own tool (used 2026-08-05)
- [ ] A prospect asked a question I couldn't answer with data, so I built the measurement
- [ ] The thing I believed about SEO that turned out to be wrong when measured
- [ ] Why our analytics under-report AI traffic, and by roughly how much
- [ ] A bug in my own tool that would have given a client bad advice — and what I changed
- [ ] What a Bangladeshi B2B buyer actually does before contacting a vendor
- [ ] The difference between ranking and being cited, with numbers
- [ ] Why I removed a feature instead of shipping it
- [ ] What "AI-ready content" means concretely, at the markup level
- [ ] A competitor comparison I ran that didn't flatter us

## Before handing it over

State plainly that **you cannot publish to LinkedIn** — there is no integration. Write the
post to a file, give him the path, and let him paste it.

Flag anything in the draft that exposes the company publicly (a poor score, an internal
mistake) so he can decide, rather than deciding for him.
