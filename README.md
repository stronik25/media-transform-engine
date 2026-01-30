# Media Transformation Engine — Contract

## Outcome
When a source video is provided in input/video/, the pipeline deterministically produces:
- a clipped video
- thumbnails
- metadata (JSON)
and passes acceptance checks, or fails fast with a clear reason.

## Acceptance Criteria (Definition of Done)
A. Transform
1. Produces:
   - output/video/*.mp4 (non-empty)
   - output/thumb/* (>=1, non-empty)
   - output/meta/*.json (valid JSON)
2. Clip duration equals TARGET_SECONDS within EPS seconds.
3. Video is readable by ffprobe (no corruption).
4. Metadata JSON is valid and includes:
   - source_path
   - clip_path
   - thumb_paths
   - created_at_utc
   - run_id

B. Reliability
5. Re-running on the same input does not break; output is overwritten locally but uses unique run_id in metadata.
6. If input is missing, job fails fast with a clear error.

C. Governance
7. Code changes are restricted to allowlist.
8. CI checks must be green for PR to be mergeable.

## Non-goals
- No trend discovery.
- No auto posting to social platforms.
- No scene detection.
- No UI.

## Constraints
- Runner: ubuntu-latest
- Tools: bash, ffmpeg, jq, python3
- Stable output dirs: output/video, output/thumb, output/meta
- Deterministic defaults; no “creative” decisions.
