# Contributing to OmniRank

Thanks for helping. This document covers what a good contribution looks like here.

## Before you start

Open an issue first for anything beyond a typo. For a new stack adapter, use the
**Adapter request** template so we can agree the surface before you write code.

v0.1.0 ships exactly two skills: `audit` and `geo-artifacts`. Everything else listed in
the README's Roadmap table (`aeo-onpage`, `indexing`, `offsite-entity`, `measure`,
`smm-content`, `smm-publish`) is planned, not present. Do not write documentation or
issue text implying they already exist.

## Development setup

```bash
make install                  # editable Python install with dev extras
make test                     # full pytest suite
cd scripts/node && pnpm install && pnpm vitest run
```

## Non-negotiables

These are not style preferences. A pull request that breaks one will not be merged.

1. **Never fabricate data.** No invented statistics, ratings, reviews, testimonials or
   contributors. `facts.statistics` carries only entries marked published. An
   `AggregateRating` without a real `ratingCount` is an error, not a warning.
2. **Never claim an unevaluated gate passed.** If a URL was unreachable, that is an error
   finding. Layers whose gates did not run are absent from the score map.
3. **Secrets are `env:` pointers only.** A literal secret must fail schema validation.
4. **Missing credentials fail loudly.** Never skip silently — a skipped submission and a
   successful one look identical in logs otherwise.
5. **Finding ids are permanent.** `<layer>.<gate>.<condition>`. Renaming a released id
   breaks every consumer that joins on it.

## Tests

Test-driven, please: a failing test first, then the implementation. A gate that has never
failed has never been proven to work.

Tests must not touch the live network. Use `respx` for httpx and local HTML fixtures.

## Commits

Conventional-commit prefixes (`feat:`, `fix:`, `docs:`, `test:`, `chore:`). Keep them small
and scoped.
