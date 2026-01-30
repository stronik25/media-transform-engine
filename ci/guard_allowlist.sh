#!/usr/bin/env bash
set -euo pipefail

ALLOWLIST_FILE=".ai/allowlist.txt"
BASE_REF="${BASE_REF:-origin/main}"

if [ ! -f "$ALLOWLIST_FILE" ]; then
  echo "Missing $ALLOWLIST_FILE"
  exit 1
fi

git fetch origin main --quiet || true

CHANGED="$(git diff --name-only "$BASE_REF"...HEAD || true)"
if [ -z "${CHANGED// }" ]; then
  echo "No changes detected."
  exit 0
fi

is_allowed () {
  local path="$1"
  while IFS= read -r rule; do
    [ -z "$rule" ] && continue
    python3 - "$path" "$rule" <<'PY' | grep -q OK && return 0 || true
import fnmatch, sys
path=sys.argv[1]
rule=sys.argv[2].strip()
rule2=rule.replace("/**","/*")
ok = fnmatch.fnmatch(path, rule2) or fnmatch.fnmatch(path, rule)
print("OK" if ok else "NO")
PY
  done < "$ALLOWLIST_FILE"
  return 1
}

BAD=0
echo "Changed files:"
echo "$CHANGED"
echo ""

while IFS= read -r f; do
  [ -z "$f" ] && continue
  if ! is_allowed "$f"; then
    echo "NOT ALLOWED: $f"
    BAD=1
  fi
done <<< "$CHANGED"

if [ "$BAD" -ne 0 ]; then
  echo ""
  echo "Allowlist violation."
  exit 2
fi

echo "Allowlist OK."
