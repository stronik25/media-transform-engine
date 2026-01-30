#!/usr/bin/env bash
set -euo pipefail

TARGET_SECONDS="${TARGET_SECONDS:-30}"
EPS="${EPS:-0.5}"

echo "== Ensure output dirs =="
test -d output/video
test -d output/thumb
test -d output/meta

V="$(ls -1 output/video/*.mp4 2>/dev/null | head -n 1 || true)"
test -n "$V"
test -s "$V"

echo "== Validate video readable =="
ffprobe -v error "$V" >/dev/null

echo "== Check duration ${TARGET_SECONDS}±${EPS} =="
DUR="$(ffprobe -v error -show_entries format=duration -of default=nw=1:nk=1 "$V")"
export DUR TARGET_SECONDS EPS
python3 - <<'PY'
import os
dur=float(os.environ["DUR"])
target=float(os.environ["TARGET_SECONDS"])
eps=float(os.environ["EPS"])
lo, hi = target-eps, target+eps
assert lo <= dur <= hi, f"Duration {dur} not in [{lo},{hi}]"
print("OK duration:", dur)
PY

echo "== Thumbs exist & non-empty =="
T="$(ls -1 output/thumb/* 2>/dev/null | head -n 1 || true)"
test -n "$T"
test -s "$T"

echo "== Meta JSON valid =="
M="$(ls -1 output/meta/*.json 2>/dev/null | head -n 1 || true)"
test -n "$M"
jq -e . "$M" >/dev/null

echo "== Meta contains required fields =="
python3 - <<'PY'
import json, glob
m=glob.glob("output/meta/*.json")[0]
data=json.load(open(m,"r",encoding="utf-8"))
required=["source_path","clip_path","thumb_paths","created_at_utc","run_id"]
missing=[k for k in required if k not in data]
assert not missing, f"Missing fields: {missing}"
assert isinstance(data["thumb_paths"], list) and len(data["thumb_paths"])>=1, "thumb_paths invalid"
print("OK meta fields")
PY

echo "ALL ACCEPTANCE CHECKS PASSED"
