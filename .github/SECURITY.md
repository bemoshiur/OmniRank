# Security Policy

## Supported versions

| Version | Supported |
|---|---|
| 0.1.x | Yes |

## Reporting a vulnerability

Please do **not** open a public issue for a security problem.

Email **moshiur@ticonsys.com** with a description, reproduction steps, and the impact
you have assessed. You can expect an acknowledgement within 72 hours and an assessment
within seven days.

## Scope

v0.1.0 ships only the `audit` and `geo-artifacts` skills, and neither reads a credential
or calls a third-party API today — `Config.secret()` exists and is exercised by tests, but
no shipped skill calls it yet. The config schema already reserves the shape for when that
changes. The areas most worth your attention, now and as later skills land:

- **Credential leakage** — a secret appearing in a report, log, or committed file. Config
  will hold `env:` pointers only; a literal secret is rejected at schema validation.
- **SSRF via configured URLs** — the crawler follows URLs from config and sitemaps.
- **Write-scope escalation** — anything letting a non-publishing skill perform a network
  write. No publishing skill ships until v0.7; when one does, it will be gated by design:
  dry-run default, explicit human approval, and confirmation before any outward write.

## Out of scope

Rate limits imposed by third-party APIs, and findings that require an attacker to already
control the machine running OmniRank.
