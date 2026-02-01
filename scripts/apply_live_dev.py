#!/usr/bin/env python3
from __future__ import annotations

import hashlib
import json
import os
import shutil
import subprocess
import sys
from pathlib import Path

from scripts.gh_api import request_json


def die(msg: str, code: int = 2) -> None:
    print(msg, file=sys.stderr)
    raise SystemExit(code)


def sha256_file(p: Path) -> str:
    h = hashlib.sha256()
    with p.open("rb") as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def safe_mkdir(p: Path) -> None:
    p.mkdir(parents=True, exist_ok=True)


def validate_and_normalize(art_dir: Path, issue: str) -> dict:
    if not art_dir.exists() or not art_dir.is_dir():
        die(f"Artifact dir not found: {art_dir}")

    # Expected: issue_1.md, request.json, response.json
    issue_md = art_dir / f"issue_{issue}.md"
    req = art_dir / "request.json"
    resp = art_dir / "response.json"

    missing = [str(p) for p in (issue_md, req, resp) if not p.exists()]
    if missing:
        die("ERROR: missing artifact files:\n" + "\n".join(missing), code=11)

    # Normalize: ensure files are plain files
    for p in (issue_md, req, resp):
        if not p.is_file():
            die(f"ERROR: not a file: {p}", code=12)

    # Validate JSON parseability
    for jp in (req, resp):
        try:
            json.loads(jp.read_text(encoding="utf-8"))
        except Exception as ex:
            die(f"ERROR: invalid json: {jp} ({ex})", code=13)

    dig = {
        "issue_md_sha256": sha256_file(issue_md),
        "request_json_sha256": sha256_file(req),
        "response_json_sha256": sha256_file(resp),
    }
    digest_line = hashlib.sha256(
        (dig["issue_md_sha256"] + dig["request_json_sha256"] + dig["response_json_sha256"]).encode("utf-8")
    ).hexdigest()

    return {
        "issue": issue,
        "artifact_dir": str(art_dir),
        "files": {"issue_md": str(issue_md), "request": str(req), "response": str(resp)},
        "digests": dig,
        "apply_digest": digest_line,
    }


def write_apply_digest(repo_root: Path, digest: str) -> None:
    out_dir = repo_root / "output"
    safe_mkdir(out_dir)
    (out_dir / "apply_digest.txt").write_text(digest + "\n", encoding="utf-8")


def apply_into_repo(repo_root: Path, art_dir: Path, issue: str, meta: dict) -> None:
    # Where to apply in repo
    ai_dir = repo_root / ".ai" / "dev"
    safe_mkdir(ai_dir)

    src_issue = art_dir / f"issue_{issue}.md"
    src_req = art_dir / "request.json"
    src_resp = art_dir / "response.json"

    dst_issue = ai_dir / f"issue_{issue}.md"
    dst_req = ai_dir / "request.json"
    dst_resp = ai_dir / "response.json"

    shutil.copy2(src_issue, dst_issue)
    shutil.copy2(src_req, dst_req)
    shutil.copy2(src_resp, dst_resp)

    # Also write digest
    write_apply_digest(repo_root, meta["apply_digest"])


def run(cmd: list[str], cwd: Path | None = None) -> None:
    subprocess.run(cmd, cwd=str(cwd) if cwd else None, check=True)


def git(*args: str) -> None:
    run(["git", *args])


def create_branch_commit_push(repo_root: Path, branch: str, base_branch: str, message: str) -> None:
    git("checkout", base_branch)
    git("checkout", "-B", branch)

    git("add", ".ai/dev", "output/apply_digest.txt")
    git("status", "--porcelain")

    # Commit even if small change set
    git("commit", "-m", message)
    git("push", "-f", "origin", branch)


def open_pr_and_comment(token: str, owner: str, repo: str, issue: str, head: str, base: str, body: str) -> None:
    pr_url = f"https://api.github.com/repos/{owner}/{repo}/pulls"
    status, parsed, raw = request_json(
        "POST",
        pr_url,
        token,
        {"title": f"ai-live: issue #{issue} ({head})", "head": head, "base": base, "body": body},
    )
    if status not in (200, 201) or not parsed or "html_url" not in parsed:
        die(f"ERROR: PR create failed. status={status} body={raw}", code=31)

    pr_link = parsed["html_url"]

    c_url = f"https://api.github.com/repos/{owner}/{repo}/issues/{issue}/comments"
    status2, _, raw2 = request_json("POST", c_url, token, {"body": f"Opened PR: {pr_link}"})
    if status2 not in (200, 201):
        die(f"ERROR: comment failed. status={status2} body={raw2}", code=32)


def main() -> None:
    mode = (sys.argv[1] if len(sys.argv) > 1 else "").strip()
    if mode not in ("validate", "apply"):
        die("Usage: scripts/apply_live_dev.py validate|apply")

    repo_root = Path(os.getcwd()).resolve()
    issue = (os.environ.get("ISSUE") or "").strip()
    run_id = (os.environ.get("RUN_ID") or "").strip()
    art_dir = Path((os.environ.get("ART_DIR") or "").strip())

    if not issue or not run_id or not str(art_dir):
        die("Missing env: ISSUE, RUN_ID, ART_DIR")

    meta = validate_and_normalize(art_dir, issue)
    # Always write digest during validate so you can see it in logs/artifacts if needed
    write_apply_digest(repo_root, meta["apply_digest"])

    print(f"OK: validated artifact for issue={issue} run_id={run_id}")
    print(f"apply_digest={meta['apply_digest']}")

    if mode == "validate":
        return

    # apply mode
    apply_into_repo(repo_root, art_dir, issue, meta)

    token = os.environ.get("GH_TOKEN") or os.environ.get("GITHUB_TOKEN")
    owner = os.environ.get("OWNER")
    repo = os.environ.get("REPO")
    base_branch = (os.environ.get("BASE_BRANCH") or "main").strip()

    if not token or not owner or not repo:
        die("Missing env for apply: GH_TOKEN, OWNER, REPO")

    branch = f"ai-live/issue-{issue}-run-{run_id}"
    msg = f"apply-live: issue #{issue} from run {run_id}"
    pr_body = (
        f"Apply LIVE DEV artifact 'live-dev' from workflow run {run_id}.\n\n"
        f"Digest: `{meta['apply_digest']}`\n"
    )

    create_branch_commit_push(repo_root, branch, base_branch, msg)
    open_pr_and_comment(token, owner, repo, issue, branch, base_branch, pr_body)
    print("OK: applied + PR opened")


if __name__ == "__main__":
    main()
