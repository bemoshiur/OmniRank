# Brand assets

## og.png — social preview

`og-template.svg` is the source. Render it with:

```bash
./scripts/render-og.sh
```

Output is `og.png` at 1280×640 — GitHub's recommended size, and it must stay under 1 MB.

## Uploading it

**GitHub has no API for the social preview image.** There is no REST or GraphQL endpoint
for it, and `gh repo edit` cannot set it either. This step cannot be automated — it must be
done by hand, every time the image changes:

1. Open <https://github.com/bemoshiur/OmniRank/settings>
2. Scroll to **Social preview**
3. **Edit** → **Upload an image** → choose `.github/assets/og.png`

Verify afterwards by pasting the repo URL into any chat app and checking the unfurl.

## Reuse

The same SVG feeds release banners. Change the tagline text and re-render.
