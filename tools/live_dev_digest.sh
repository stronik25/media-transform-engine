#!/usr/bin/env bash
set -euo pipefail

# Usage:
#   tools/live_dev_digest.sh <artifact_dir>
#
# Contract (required in artifact_dir):
#   - request.json
#   - response.json
#   - apply_digest.txt
#   - issue_*.md (>=1)
#
# Digest rule (v1):
#   - include files in this order:
#       1) issue_*.md (sorted by name, C-locale)
#       2) request.json
#       3) response.json
#   - for each file compute sha256(file_bytes)
#   - manifest lines (LF): "<sha256>␠␠<relative_path>\n"
#   - final digest = sha256(manifest_bytes)
#
# apply_digest.txt accepted:
#   - "<hex64>"
#   - "sha256:<hex64>"

export LC_ALL=C

ART_DIR="${1:-}"
if [[ -z "${ART_DIR}" ]]; then
  echo "ERROR: missing artifact_dir"
  exit 2
fi
if [[ ! -d "${ART_DIR}" ]]; then
  echo "ERROR: artifact_dir not found: ${ART_DIR}"
  exit 2
fi

cd "${ART_DIR}"

# Required files
[[ -f "request.json" ]] || { echo "ERROR: missing request.json"; exit 3; }
[[ -f "response.json" ]] || { echo "ERROR: missing response.json"; exit 3; }
[[ -f "apply_digest.txt" ]] || { echo "ERROR: missing apply_digest.txt"; exit 3; }

# issue_*.md >= 1 (stable order)
mapfile -t ISSUE_FILES < <(ls -1 issue_*.md 2>/dev/null | sort || true)
if [[ "${#ISSUE_FILES[@]}" -lt 1 ]]; then
  echo "ERROR: missing issue_*.md"
  exit 3
fi

# Read expected digest: first non-empty trimmed line/token, strip CR
EXPECTED_RAW="$(
  tr -d '\r' < apply_digest.txt \
  | sed -e 's/^[[:space:]]*//' -e 's/[[:space:]]*$//' \
  | awk 'NF { print $0; exit }' \
  || true
)"

if [[ -z "${EXPECTED_RAW}" ]]; then
  echo "ERROR: apply_digest.txt is empty"
  exit 3
fi

EXPECTED="${EXPECTED_RAW#sha256:}"

# Validate sha256 hex length
if ! [[ "${EXPECTED}" =~ ^[a-fA-F0-9]{64}$ ]]; then
  echo "ERROR: apply_digest.txt invalid format: ${EXPECTED_RAW}"
  exit 3
fi

# Build ordered file list
FILES=()
for f in "${ISSUE_FILES[@]}"; do FILES+=("$f"); done
FILES+=("request.json")
FILES+=("response.json")

# Build manifest in temp file (stable bytes)
MANIFEST_FILE="$(mktemp)"
cleanup() { rm -f "${MANIFEST_FILE}"; }
trap cleanup EXIT

for f in "${FILES[@]}"; do
  if [[ ! -f "$f" ]]; then
    echo "ERROR: listed file missing: $f"
    exit 3
  fi
  H="$(sha256sum "$f" | awk '{print $1}')"
  # Force LF line endings regardless of platform
  printf "%s  %s\n" "$H" "$f" >> "${MANIFEST_FILE}"
done

ACTUAL="$(sha256sum "${MANIFEST_FILE}" | awk '{print $1}')"

echo "expected: ${EXPECTED_RAW}"
echo "actual:   sha256:${ACTUAL}"

if [[ "${ACTUAL,,}" != "${EXPECTED,,}" ]]; then
  echo "ERROR: digest mismatch"
  exit 4
fi

echo "OK: live-dev contract + digest verified"
