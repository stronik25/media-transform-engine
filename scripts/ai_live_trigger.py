#!/usr/bin/env python3
from __future__ import annotations

import json
import os
import re
import sys

from scripts.gh_api import request_json


def die(msg: str, code: int = 2) -> None:
    print(msg, file=sys.stderr)
    raise SystemExit(code)


def main() -> None:
    token = os.environ.get("GH_TOKEN") or os.environ.get("GITHUB_TOKEN")
    owner = os.environ.get("OWNER")
    repo = os.environ.get("REPO")
    event_name = os.environ.get("EVENT_NAME") or os.environ.get("GITHUB_EVENT_NAME")
    event_path = os.environ.get("EVENT_PATH") or os.environ.get("GITHUB_EVENT_PATH")

    if not token or not owner or not repo or not event_name or not event_path:
        die("Missing required env: GH_TOKEN/OWNER/REPO/EVENT_NAME/EVENT_PATH")

    with open(event_path, "r", encoding="utf-8") as f:
        e = json.load(f)

    trigger_label = os.environ.get("TRIGGER_LABEL", "ai-live")
    wf_file = os.environ.get("AI_DEBUG_WORKFLOW_FILE", "ai-debug-3agents.yml")
    ref = os.environ.get("REF", "main")

    # Extract common fields
    issue_num = str((e.get("issue") or {}).get("number") or "").strip()
    label_name = str((e.get("label") or {}).get("name") or "").strip()
    comment_body = str(((e.get("comment") or {}).get("body") or "")).replace("\r", "")
    author_assoc = str((e.get("comment") or {}).get("author_association") or "").strip()

    if not issue_num:
        print("No issue number in event; nothing to do.")
        return

    should = False
    reason = ""

    if event_name == "issues":
        if label_name == trigger_label:
            should = True
            reason = "label"
        else:
            should = False
            reason = "label_mismatch"

    elif event_name == "issue_comment":
        assoc = author_assoc.lower()
        if assoc not in ("owner", "member", "collaborator"):
            should = False
            reason = "untrusted_author_association"
        else:
            if re.search(r"(^|\s)/ai\s+live(-run)?(\s|$)", comment_body):
                should = True
                reason = "comment"
            else:
                should = False
                reason = "comment_no_match"
    else:
        should = False
        reason = f"unsupported_event:{event_name}"

    print(f"should_dispatch={should} reason={reason} issue_num={issue_num}")

    if not should:
        return

    # Dispatch AI Debug
    url = f"https://api.github.com/repos/{owner}/{repo}/actions/workflows/{wf_file}/dispatches"
    payload = {
        "ref": ref,
        "inputs": {
            "issue": issue_num,
            "run_live": "true",
            "apply_live": "false",
            "live_max_usd": os.environ.get("DEFAULT_MAX_USD", "0.50"),
            "live_max_input_tokens": os.environ.get("DEFAULT_MAX_IN", "12000"),
            "live_max_output_tokens": os.environ.get("DEFAULT_MAX_OUT", "1200"),
            "live_fail_on_cap": os.environ.get("DEFAULT_FAIL_ON_CAP", "true"),
        },
    }

    status, parsed, raw = request_json("POST", url, token, payload)
    if status != 204:
        die(f"Dispatch failed. status={status} body={raw}")

    # Comment back
    wf_link = f"https://github.com/{owner}/{repo}/actions/workflows/{wf_file}"
    msg = (
        f"Dispatched AI Debug LIVE run (no apply). Trigger={reason}. "
        f"Track runs: {wf_link}. Next: run apply-live.yml by run_id after live-dev exists."
    )
    c_url = f"https://api.github.com/repos/{owner}/{repo}/issues/{issue_num}/comments"
    status2, _, raw2 = request_json("POST", c_url, token, {"body": msg})
    if status2 not in (200, 201):
        die(f"Comment failed. status={status2} body={raw2}")

    # Remove label if it was the arm
    if event_name == "issues":
        d_url = f"https://api.github.com/repos/{owner}/{repo}/issues/{issue_num}/labels/{trigger_label}"
        status3, _, raw3 = request_json("DELETE", d_url, token, None)
        # GitHub may return 200 or 204
        if status3 not in (200, 204):
            print(f"WARN: label remove failed. status={status3} body={raw3}", file=sys.stderr)


if __name__ == "__main__":
    main()
