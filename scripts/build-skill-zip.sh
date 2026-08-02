#!/usr/bin/env bash
# Build a downloadable Claude-skill ZIP for OmniRank.
#
# Usage: scripts/build-skill-zip.sh [version]
#   version   optional; defaults to the "version" field in
#             .claude-plugin/plugin.json
#
# Stages a top-level `omnirank/` folder containing the pieces a user needs
# to install the skill without cloning the repo, strips build/cache
# artifacts, zips it, and writes dist/omnirank-skill-<version>.zip.

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ROOT="$(cd "${SCRIPT_DIR}/.." && pwd)"
cd "${ROOT}"

PLUGIN_JSON="${ROOT}/.claude-plugin/plugin.json"

if [[ $# -ge 1 ]]; then
  VERSION="$1"
else
  if [[ ! -f "${PLUGIN_JSON}" ]]; then
    echo "ERROR: no version given and ${PLUGIN_JSON} does not exist" >&2
    exit 1
  fi
  VERSION="$(python3 -c "import json; print(json.load(open('${PLUGIN_JSON}'))['version'])")"
fi

DIST_DIR="${ROOT}/dist"
OUT_ZIP="${DIST_DIR}/omnirank-skill-${VERSION}.zip"

WORK_DIR="$(mktemp -d)"
trap 'rm -rf "${WORK_DIR}"' EXIT

STAGE="${WORK_DIR}/omnirank"
mkdir -p "${STAGE}"

# Paths staged into the release, relative to repo root. Missing ones are
# skipped without failing the build (README.md / LICENSE arrive later).
ITEMS=(
  ".claude-plugin"
  "skills"
  "scripts/py"
  "schemas"
  "templates"
  "README.md"
  "LICENSE"
  "LICENSE-CONTENT"
  "Makefile"
)

for item in "${ITEMS[@]}"; do
  src="${ROOT}/${item}"
  if [[ ! -e "${src}" ]]; then
    echo "skip: ${item} (not present yet)" >&2
    continue
  fi
  dest="${STAGE}/${item}"
  mkdir -p "$(dirname "${dest}")"
  cp -R "${src}" "${dest}"
done

# Strip build/cache artifacts that must never ship in the release zip.
find "${STAGE}" -depth -type d \
  \( -name "__pycache__" -o -name ".pytest_cache" -o -name "*.egg-info" -o -name ".venv" \
     -o -name ".ruff_cache" \) \
  -exec rm -rf {} +
find "${STAGE}" -type f -name "*.pyc" -delete

mkdir -p "${DIST_DIR}"
rm -f "${OUT_ZIP}"

(cd "${WORK_DIR}" && zip -rq "${OUT_ZIP}" "omnirank")

if [[ ! -s "${OUT_ZIP}" ]]; then
  echo "ERROR: ${OUT_ZIP} was not created or is empty" >&2
  exit 1
fi

LISTING="$(unzip -l "${OUT_ZIP}")"
if ! grep -q "omnirank/.claude-plugin/plugin.json" <<< "${LISTING}"; then
  echo "ERROR: ${OUT_ZIP} does not contain omnirank/.claude-plugin/plugin.json" >&2
  exit 1
fi

SIZE="$(du -h "${OUT_ZIP}" | cut -f1 | tr -d ' ')"
echo "Built: ${OUT_ZIP} (${SIZE})"
