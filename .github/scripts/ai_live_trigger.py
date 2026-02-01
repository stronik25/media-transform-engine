#!/usr/bin/env python3
import json
import os
import re
import sys
import urllib.request
import urllib.error

TRUSTED_ASSOC = {"OWNER", "MEMBER", "COLLABORATOR"}


def gh_api(method: str, url: str, token: str, payload: dict | None = None) -> tuple[int, str]:
    data = None
    headers = {
        "Authorization": f"Bearer {token}",
        "Accept": "application/vnd.github+json",
        "User-Agent": "ai-live-trigger",
    }
    if payload is not None:
        body = json.dumps(payload).encode("utf-8")
        data = body
        headers["Content-Type"] = "application/json"

    req = urllib.request.Request(url=url, data=data, method=method, headers=headers)
    try:
        with urllib.request.urlopen(req) as resp:
            return resp.getcode(), resp.read().decode("utf-8", errors="replace")
    except urllib.error.HTTPError as e:
        return e.code, e.read().decode("utf-8", errors="replace")
    except Exception as e:
        return 0, f"{type(e).__name__}: {e}"


def main() -> int:
    token = os.environ.get("GH_TOKEN", "").strip()
    if not token:
        print("ERROR: GH_TOKEN is missing", file=sys.stderr)
        return 2

    event_path = os.environ.get("EVENT_PATH") or os.environ.get("GITHUB_EVENT_PATH")
    if not event_path:
        print("ERROR: EVENT_PATH/GITHUB_EVENT_PATH missing", file=sys.stderr)
        return 2

    with open(event_path, "r", encoding="utf-8") as f:
        event = json.load(f)

    repo = os.environ.get("GITHUB_REPOSITORY", "").strip()
    if not repo or "/" not in repo:
        print("ERROR: GITHUB_REPOSITORY missing/invalid", file=sys.stderr)
        return 2
    owner, name = repo.split("/", 1)

    trigger_label = os.environ.get("TRIGGER_LABEL", "ai-live")
    ref = os.environ.get("REF", "main")
    wf_file = os.environ.get("AI_DEBUG_WORKFLOW_FILE", "ai-debug-3agents.yml")

    default_max_usd = os.environ.get("DEFAULT_MAX_USD", "0.50")
    default_in = os.environ.get("DEFAULT_MAX_IN", "12000")
    default_out = os.environ.get("DEFAULT_MAX_OUT", "1200")
    default_fail_on_cap = os.environ.get("DEFAULT_FAIL_ON_CAP", "true")

    event_name = os.environ.get("EVENT_NAME") or os.environ.get("GITHUB_EVENT_NAME") or ""
    issue_num = str((event.get("issue") or {}).get("number") or "").strip()

    if not issue_num:
        print("Not dispatching: no issue number")
        return 0

    should = False
    reason = "no_match"

    if event_name == "issues":
        label_name = str((event.get("label") or {}).get("name") or "").strip()
        if label_name == trigger_label:
            should = True
            reason = "label"
        else:
            reason = "label_mismatch"

    elif event_name == "issue_comment":
        comment = event.get("comment") or {}
        assoc = str(comment.get("author_association") or "").strip()
        if assoc not in TRUSTED_ASSOC:
            print(f"Not dispatching: untrusted author_association={assoc}")
            return 0

        body = str(comment.get("body") or "").replace("\r", "")
        if re.search(r"(^|\s)/ai\s+live(-run)?(\s|$)", body):
            should = True
            reason = "comment"
        else:
            reason = "comment_no_match"

    else:
        print(f"Not dispatching: unsupported event_name={event_name}")
        return 0

    if not should:
        print(f"Not dispatching: reason={reason}")
        return 0

    dispatch_url = f"https://api.github.com/repos/{owner}/{name}/actions/workflows/{wf_file}/dispatches"
    payload = {
        "ref": ref,
        "inputs": {
            "issue": issue_num,
            "run_live": "true",
            "apply_live": "false",
            "live_max_usd": default_max_usd,
            "live_max_input_tokens": default_in,
            "live_max_output_tokens": default_out,
            "live_fail_on_cap": default_fail_on_cap,
        },
    }

    code, body = gh_api("POST", dispatch_url, token, payload)
    if code != 204:
        print(f"ERROR: dispatch failed http={code}", file=sys.stderr)
        print(body, file=sys.stderr)
        return 7

    # comment back
    issue_comments_url = f"https://api.github.com/repos/{owner}/{name}/issues/{issue_num}/comments"
    wf_link = f"https://github.com/{owner}/{name}/actions/workflows/{wf_file}"
    msg = (
        f"Dispatched AI Debug LIVE run (no apply). Trigger={reason}. "
        f"Track runs: {wf_link}. Next: run apply-live.yml by run_id after live-dev exists."
    )
    c_code, c_body = gh_api("POST", issue_comments_url, token, {"body": msg})
    if c_code not in (200, 201):
        print(f"WARN: failed to comment back http={c_code}", file=sys.stderr)
        print(c_body, file=sys.stderr)

    # remove label for one-shot arming (only when label event)
    if event_name == "issues" and reason == "label":
        rm_url = f"https://api.github.com/repos/{owner}/{name}/issues/{issue_num}/labels/{trigger_label}"
        rm_code, _ = gh_api("DELETE", rm_url, token, None)
        if rm_code not in (200, 204):
            print(f"WARN: failed to remove label http={rm_code}", file=sys.stderr)

    print("OK: dispatched")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
