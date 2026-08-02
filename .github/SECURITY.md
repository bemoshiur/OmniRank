# Security Policy

## Supported versions

| Version | Supported |
|---|---|
| 0.1.x | Yes |

## Reporting a vulnerability

Please do **not** open a public issue for a security problem.

Email **moshiur@publicpulse.com.bd** with a description, reproduction steps, and the impact
you have assessed. You can expect an acknowledgement within 72 hours and an assessment
within seven days.

## Scope

OmniRank reads credentials from environment variables and talks to third-party APIs. The
areas most worth your attention:

- **Credential leakage** — a secret appearing in a report, log, or committed file. Config
  must hold `env:` pointers only; a literal secret is rejected at schema validation.
- **SSRF via configured URLs** — the crawler follows URLs from config and sitemaps.
- **Write-scope escalation** — anything letting a non-publishing skill perform a network
  write. Publishing skills are gated by design: dry-run default, explicit human approval,
  and confirmation before any outward write.

## Out of scope

Rate limits imposed by third-party APIs, and findings that require an attacker to already
control the machine running OmniRank.
