# facts.json

Structured ground truth for engines that prefer JSON over prose.

## Shape

```json
{
  "name": "The Pulse Today",
  "url": "https://pulsetoday.com.bd",
  "entityType": "NewsMediaOrganization",
  "generatedAt": "2026-08-03T04:00:00Z",
  "license": "CC-BY-4.0",
  "attribution": "Public Pulse Agency",
  "legalName": "Public Pulse Agency",
  "locales": [{ "code": "bn-BD", "path": "/bn", "default": true }],
  "nap": { "city": "Dhaka", "country": "BD", "email": "editor@pulsetoday.com.bd" },
  "identifiers": { "bin": "123456", "tradeLicense": "789012" },
  "sameAs": ["https://facebook.com/ThePulseToday"],
  "statistics": [
    { "name": "Average CPM, political FB ads, Dhaka",
      "value": "BDT 42", "unit": "BDT", "sampleSize": 118,
      "methodology": "Meta Ads Library, 90-day trailing average",
      "asOf": "2026-07-01", "source": "internal", "published": true }
  ]
}
```

`name`, `url`, `entityType`, `generatedAt`, `license`, and `attribution` are always
present. `legalName`, `locales`, `nap`, `identifiers`, `sameAs`, and `statistics` are each
omitted entirely when the underlying config has nothing to say — never emitted as an empty
string, array, or object.

## The `statistics` item shape

Each entry in `omnirank.config.json`'s top-level `statistics` array requires `name` and
`value`. `unit`, `sampleSize`, `methodology`, `asOf`, `source`, and `published` are all
optional. Whatever fields an entry carries — including `published` itself — pass straight
through into `facts.json` unchanged; nothing is stripped before it reaches the file.

## Field rules

| Field | Rule |
|---|---|
| `sameAs` | Non-null values only. Nulls in config are the entity worklist, not data. |
| `statistics` | Only entries with `published: true`. Omit the key entirely when none qualify. |
| `identifiers` | Real registration numbers only. These say "a real registered entity exists." |
| `license` + `attribution` | Always present. This is the permission signal. |
| `generatedAt` | Regenerated every build, so staleness is visible. |

## Why the published gate matters

First-party data is the strongest GEO asset available — nobody else has your numbers. That
advantage exists only while every number is true. One invented statistic, discovered once,
costs more trust than ten real ones earn.

Fill in `value`, `sampleSize`, and `methodology`, then flip `published: true`. Until then
the statistic renders nowhere.
