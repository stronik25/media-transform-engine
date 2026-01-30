#!/usr/bin/env bash
set -euo pipefail

TARGET_SECONDS="${TARGET_SECONDS:-30}"

mkdir -p output/video output/thumb output/meta

SRC="$(find input/video -type f \( -name '*.mp4' -o -name '*.mov' -o -name '*.mkv' \) | sort | head -n 1 || true)"
if [ -z "${SRC}" ]; then
  echo "ERROR: No input video found under input/video/"
  exit 10
fi

RUN_ID="${GITHUB_RUN_ID:-local-$(date -u +%Y%m%dT%H%M%SZ)}"
NOW="$(date -u +%Y-%m-%dT%H:%M:%SZ)"

OUTV="output/video/clip_${RUN_ID}.mp4"

# Clip first TARGET_SECONDS seconds, normalize to H.264/AAC
ffmpeg -y -hide_banner -loglevel error \
  -i "$SRC" \
  -t "$TARGET_SECONDS" \
  -c:v libx264 -preset veryfast -pix_fmt yuv420p \
  -c:a aac -b:a 128k \
  "$OUTV"

# Thumbnails (fps=1)
THUMB_DIR="output/thumb"
ffmpeg -y -hide_banner -loglevel error \
  -i "$OUTV" \
  -vf "fps=1,scale=640:-1" \
  "${THUMB_DIR}/thumb_${RUN_ID}_%03d.jpg"

# Metadata
export RUN_ID SRC OUTV NOW
python3 - <<'PY'
import glob, json, os
run_id=os.environ["RUN_ID"]
src=os.environ["SRC"]
outv=os.environ["OUTV"]
now=os.environ["NOW"]
thumbs=sorted(glob.glob(f"output/thumb/thumb_{run_id}_*.jpg"))
meta={
  "source_path": src,
  "clip_path": outv,
  "thumb_paths": thumbs,
  "created_at_utc": now,
  "run_id": run_id
}
open(f"output/meta/meta_{run_id}.json","w",encoding="utf-8").write(json.dumps(meta,ensure_ascii=False,indent=2))
print("thumb_count",len(thumbs))
PY
