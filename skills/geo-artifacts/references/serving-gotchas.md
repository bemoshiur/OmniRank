# Serving gotchas

## The OpenNext / CloudFront 403

**Symptom:** `/llms.txt` returns 200 but `/llms-full.txt` returns **403**, and it works
perfectly in local development.

**Cause:** the CDN routes requests by path extension. On OpenNext + CloudFront + S3, `.txt`
and `.json` paths are sent to the **S3 origin**, not the Lambda that renders dynamic
routes. A dynamic route at that path is never reached; S3 answers for a key that does not
exist, and returns 403 rather than 404.

**Why it goes unnoticed:** local `next dev` has no CDN, so the dynamic route serves fine.
The failure exists only in production. On publicpulse.com.bd this left `/llms-full.txt`
dead for weeks while every local check passed.

**Fix:** write the file physically into `publicDir` at build time so S3 has a real object
to serve.

**Detection:** the `audit` skill reports a 403 on `llms-full.txt` or `facts.json` as
`geo.llms-full.forbidden` / `geo.facts.forbidden` — distinct from `geo.llms-full.missing` /
`geo.facts.missing` (any other non-200 status), precisely because the cause and the fix
differ. `llms.txt` has no distinguishable 403 variant: a 403 there is reported as
`geo.llms.missing` like any other non-200. See the audit skill's `references/gates.md`
for the full id table.

## The build-hook trap

OpenNext invokes `next build` directly. It does **not** run `npm run build`, so an npm
`prebuild` script never fires during deployment.

Wire generation into both:

1. `package.json` → `"prebuild": "node scripts/generate-artifacts.mjs"` — covers local
   builds and CI.
2. The deploy script, before `sst deploy` — covers production.

Running twice is harmless. Running zero times ships a stale corpus, and nothing in the
build output says so.

## Verify in production, not locally

A green local build is not evidence. After every deploy, `curl -I` all three paths and
confirm `200`. This is one of the gates `audit` runs.
