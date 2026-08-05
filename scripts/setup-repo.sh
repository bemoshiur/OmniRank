#!/usr/bin/env bash
# Apply OmniRank's GitHub repository metadata: description, homepage and
# topics. Idempotent: safe to re-run after changing any of the values below.
#
# Requires: gh CLI, authenticated (`gh auth status`).
#
# NOTE ON SCOPE: v0.1.0 ships exactly two skills, `audit` and `geo-artifacts`.
# The description below intentionally names only what is shipped today; it
# does not describe the six roadmap skills as if they already existed.
set -euo pipefail

REPO="bemoshiur/OmniRank"
HOMEPAGE="https://ticonsys.com"
DESCRIPTION="OmniRank -- SEO / AEO / GEO / SMM growth engine for Claude Code and Cursor. v0.1.0 ships two skills: audit (score SEO, AEO, GEO and crawl-hygiene gates) and geo-artifacts (generate llms.txt, llms-full.txt and facts.json for AI crawlers). More on the roadmap."

TOPICS=(
  seo
  aeo
  geo
  smm
  answer-engine-optimization
  generative-engine-optimization
  llms-txt
  schema-org
  json-ld
  structured-data
  claude-code
  claude-skills
  cursor
  mcp
  indexnow
  google-search-console
  ai-search
  llm-seo
  seo-tools
  nextjs
)

command -v gh >/dev/null 2>&1 || { echo "gh CLI not found" >&2; exit 1; }

# `gh auth status` prints to stderr and exits non-zero when unauthenticated;
# capture it instead of piping straight into a pager/grep so a broken pipe
# can never SIGPIPE the producer and trip `set -o pipefail` (exit 141).
auth_status="$(gh auth status 2>&1)" || {
  echo "gh is not authenticated:" >&2
  echo "${auth_status}" >&2
  exit 1
}

echo "==> Applying description and homepage"
gh repo edit "$REPO" \
  --description "$DESCRIPTION" \
  --homepage "$HOMEPAGE" \
  --enable-issues \
  --enable-wiki \
  --enable-discussions

echo "==> Applying ${#TOPICS[@]} topics"
topic_args=()
for topic in "${TOPICS[@]}"; do
  topic_args+=(--add-topic "$topic")
done
gh repo edit "$REPO" "${topic_args[@]}"

echo "==> Current state"
current_state="$(gh repo view "$REPO" --json name,description,homepageUrl,repositoryTopics \
  --template '{{.name}}
  {{.description}}
  {{.homepageUrl}}
  {{range .repositoryTopics}}{{.name}} {{end}}
')"
echo "${current_state}"

cat <<'MANUAL'

==> MANUAL STEPS -- GitHub has no API for these; they must be done in the UI

1. Social preview image
   https://github.com/bemoshiur/OmniRank/settings
   -> Social preview -> Edit -> Upload .github/assets/og.png
   (Render it first with ./scripts/render-og.sh)

2. Discussion categories
   https://github.com/bemoshiur/OmniRank/discussions/categories
   Create, in this order:
     Announcements         (announcement format)
     Ideas                 (open-ended)
     Q&A                   (question/answer format)
     Show and tell         (open-ended)
     Benchmarks & Evidence (open-ended)
     Adapter requests      (open-ended)
     Localization          (open-ended)

3. Seed discussion posts
     "Welcome -- what OmniRank is and is not"          -> Announcements
     "Roadmap: v0.1 to v1.0"                           -> Announcements
     "Which stack adapter should land next?"           -> Adapter requests
     "Post your AI-citation results"                   -> Benchmarks & Evidence

4. Wiki
   Publish docs/wiki/ to the .wiki remote:
     git clone https://github.com/bemoshiur/OmniRank.wiki.git /tmp/omnirank-wiki
     cp docs/wiki/*.md /tmp/omnirank-wiki/
     cd /tmp/omnirank-wiki && git add . && git commit -m "docs: sync wiki" && git push

MANUAL
