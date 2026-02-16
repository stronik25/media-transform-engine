```markdown
# Fix: AI Debug: verify clip engine end-to-end on main

URL: https://github.com/stronik25/media-transform-engine/issues/1

## Goal
- Verify the Clip Engine workflow end-to-end on the main branch after successful acceptance.
- Confirm that outputs, artifacts, and metadata fields are correct and as expected.
- If verification is successful, propose the next concrete step forward.

## Current
- Clip Engine successfully passed acceptance on main.
- No known failures at this stage.

## Expected
- Confirm outputs, artifacts, and meta fields are correct.
- If everything is green, propose the next concrete step only.

## Repro
1. Commit a valid input video longer than 30 seconds into `input/video` on main.
2. Allow the Clip Engine workflow to run automatically.

## Constraints
- Do not modify anything outside the allowlist.
- Do not change contract, prompts, or gates unless explicitly allowed.
- No speculative refactors.

## Evidence
- Green Clip Engine run:  
  https://github.com/stronik25/media-transform-engine/actions/runs/21514386367/job/61989023721
```
