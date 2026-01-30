#!/usr/bin/env bash
set -euo pipefail

OUT="${1:-ci/context.md}"

echo "# Repo Context" > "$OUT"
echo "" >> "$OUT"

add_file () {
  local f="$1"
  if [ -f "$f" ]; then
    echo "## FILE: $f" >> "$OUT"
    echo '```' >> "$OUT"
    cat "$f" >> "$OUT"
    echo '```' >> "$OUT"
    echo "" >> "$OUT"
  fi
}

add_file ".ai/contract.md"
add_file ".ai/allowlist.txt"
add_file "scripts/run_clip.sh"

for f in .github/workflows/*.yml .github/workflows/*.yaml ci/*.sh ci/*.py; do
  if [ -f "$f" ]; then add_file "$f"; fi
done

echo "## TREE (depth 4)" >> "$OUT"
echo '```' >> "$OUT"
python3 - <<'PY'
import os
max_depth=4
base="."
for root, dirs, files in os.walk(base):
    if root.startswith("./.git"):
        continue
    depth = root.count(os.sep)
    if depth>max_depth:
        dirs[:] = []
        continue
    indent = "  "*depth
    print(f"{indent}{os.path.basename(root)}/")
    for fn in sorted(files)[:100]:
        print(f"{indent}  {fn}")
PY
echo '```' >> "$OUT"
