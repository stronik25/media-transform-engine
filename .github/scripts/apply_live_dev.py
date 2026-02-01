#!/usr/bin/env python3
import hashlib
import json
import os
import subprocess
import sys
from pathlib import Path
import urllib.request
import urllib.error


def run(cmd: list[str], check: bool = True, capture: bool = False) -> subprocess.CompletedProcess:
    return subprocess.run(
        cmd,
        check=check,
        text=True,
        capture_output=capture,
    )


def gh_api(method: str, url: str, token: str, payload: dict | None = None) -> tuple[int, str]:
    data = None
    headers = {
        "Authorization": f"Bearer {token}",
        "Accept": "application/vnd.github+json",
        "User-Agent": "apply-live-dev",
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


def sha256_file(p: Path) -> str:
    h = hashlib.sha256()
    with p.open("rb") as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def main() -> int:
    repo = os.environ.get("REPO", "").strip()
    token = os.environ.get("GH_TOKEN", "").strip()
    run_id = os.environ.get("RUN_ID", "").strip()
    issue = os.environ.get("ISSUE", "").strip()
    base_branch = os.environ.get("BASE_BRANCH", "main").strip()
    dry_run = os.environ.get("DRY_RUN", "true").strip().lower() == "true"
    artifact_dir = Path(os.environ.get("ARTIFACT_DIR", "_live_dev_artifact")).resolve()

    if "/" not in repo:
        print("ERROR: REPO missing/invalid", file=sys.stderr)
        return 2
    owner, name = repo.split("/", 1)

    if not run_id.isdigit():
        print(f"ERROR: RUN_ID must be numeric, got: {run_id}", file=sys.stderr)
        return 2
    if not issue.isdigit():
        print(f"ERROR: ISSUE must be numeric, got: {issue}", file=sys.stderr)
        return 2

    if not artifact_dir.exists() or not artifact_dir.is_dir():
        print(f"ERROR: artifact dir not found: {artifact_dir}", file=sys.stderr)
        return 11

    # Expected files in artifact root:
    #  issue_1.md (or any issue_*.md), request.json, response.json
    md_files = sorted(artifact_dir.glob("issue_*.md"))
    req_json = artifact_dir / "request.json"
    resp_json = artifact_dir / "response.json"

    missing = []
    if not md_files:
        missing.append("issue_*.md")
    if not req_json.exists():
        missing.append("request.json")
    if not resp_json.exists():
        missing.append("response.json")

    if missing:
        print("ERROR: missing files in artifact:", file=sys.stderr)
        for m in missing:
            print(f" - {m}", file=sys.stderr)
        print(f"Artifact tree ({artifact_dir}):", file=sys.stderr)
        for p in sorted(artifact_dir.rglob("*")):
            print(f" - {p.relative_to(artifact_dir)}", file=sys.stderr)
        return 11

    # Pick the matching issue md if present; else first
    target_md = None
    for p in md_files:
        if p.stem == f"issue_{issue}":
            target_md = p
            break
    if target_md is None:
        target_md = md_files[0]

    # Compute digest of canonical inputs
    digest_payload = {
        "run_id": run_id,
        "issue": issue,
        "issue_md": target_md.read_text(encoding="utf-8", errors="replace"),
        "request_json": req_json.read_text(encoding="utf-8", errors="replace"),
        "response_json": resp_json.read_text(encoding="utf-8", errors="replace"),
    }
    digest_bytes = json.dumps(digest_payload, sort_keys=True).encode("utf-8")
    apply_digest = hashlib.sha256(digest_bytes).hexdigest()
    print(f"apply_digest: {apply_digest}")

    if dry_run:
        print("DRY_RUN=true -> validation only, no repo changes, no PR.")
        return 0

    # Apply into repo working tree
    ai_dev_dir = Path(".ai/dev")
    out_dir = Path("output")
    ai_dev_dir.mkdir(parents=True, exist_ok=True)
    out_dir.mkdir(parents=True, exist_ok=True)

    # Write canonical files (overwrite ok)
    dest_issue = ai_dev_dir / f"issue_{issue}.md"
    dest_req = ai_dev_dir / "request.json"
    dest_resp = ai_dev_dir / "response.json"
    dest_digest = out_dir / "apply_digest.txt"

    dest_issue.write_text(target_md.read_text(encoding="utf-8", errors="replace"), encoding="utf-8")
    dest_req.write_text(req_json.read_text(encoding="utf-8", errors="replace"), encoding="utf-8")
    dest_resp.write_text(resp_json.read_text(encoding="utf-8", errors="replace"), encoding="utf-8")
    dest_digest.write_text(apply_digest + "\n", encoding="utf-8")

    # Git branch + commit + push
    head_branch = f"ai-live/issue-{issue}-run-{run_id}"
    run(["git", "status", "--porcelain"], check=True)

    run(["git", "checkout", "-B", head_branch, base_branch], check=True)
    run(["git", "add", str(dest_issue), str(dest_req), str(dest_resp), str(dest_digest)], check=True)

    # If nothing changed, stop
    diff = run(["git", "diff", "--cached", "--name-only"], capture=True).stdout.strip()
    if not diff:
        print("No changes to commit (already applied).")
        return 0

    msg = f"apply-live: issue #{issue} from run {run_id}"
    run(["git", "commit", "-m", msg], check=True)
    run(["git", "push", "-f", "origin", head_branch], check=True)

    if not token:
        print("WARN: GH_TOKEN missing -> pushed branch but cannot open PR.", file=sys.stderr)
        return 0

    # Open PR
    pr_url = f"https://api.github.com/repos/{owner}/{name}/pulls"
    title = f"ai-live: issue #{issue} (run {run_id})"
    body = f"Apply LIVE DEV artifact 'live-dev' from workflow run {run_id}. Includes digest for traceability."
    payload = {"title": title, "head": head_branch, "base": base_branch, "body": body}

    code, resp = gh_api("POST", pr_url, token, payload)
    if code not in (200, 201):
        print(f"ERROR: failed to open PR http={code}", file=sys.stderr)
        print(resp, file=sys.stderr)
        return 13

    print("OK: PR opened")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
