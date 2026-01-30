#!/usr/bin/env bash
set -euo pipefail

# Secrets (GitHub Actions):
#   LLM_ENDPOINT (OpenAI-compatible chat completions endpoint)
#   LLM_API_KEY
#
# Optional env:
#   LLM_MODEL
#
# Args:
#   $1 = system prompt file
#   $2 = user content file
#   $3 = output file (raw JSON response)

SYS_FILE="$1"
USER_FILE="$2"
OUT_FILE="$3"

: "${LLM_ENDPOINT:?Missing LLM_ENDPOINT}"
: "${LLM_API_KEY:?Missing LLM_API_KEY}"
LLM_MODEL="${LLM_MODEL:-gpt-4.1-mini}"

SYS="$(cat "$SYS_FILE")"
USR="$(cat "$USER_FILE")"

export SYS USR LLM_MODEL

curl -sS "$LLM_ENDPOINT" \
  -H "Authorization: Bearer $LLM_API_KEY" \
  -H "Content-Type: application/json" \
  -d "$(python3 - <<'PY'
import json, os
sys=os.environ["SYS"]
usr=os.environ["USR"]
model=os.environ["LLM_MODEL"]
print(json.dumps({
  "model": model,
  "messages": [
    {"role": "system", "content": sys},
    {"role": "user", "content": usr}
  ],
  "temperature": 0
}))
PY
)" > "$OUT_FILE"
