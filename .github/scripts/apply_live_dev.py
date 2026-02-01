#!/usr/bin/env python3
from __future__ import annotations

import argparse
import os
import shutil
import subprocess
from pathlib import Path
from typing import List

from gh_api import create_pull_request, comment_issue


def sh(cmd: List[str], cwd: str | None = None) -> str:
    p = subprocess.run(cmd, cwd=cwd, check=True, capture_output=True, text=True)
    return p.stdout.strip()


def ensure_clean_paths(dest: Path) -> None:
    # We only allow writing into these prefixes (safety gate)
    allowed_prefixes = [
        Path(".ai") / "dev",
        Path("output"),
    ]
    dest_rel = dest.as_posix()
    ok = any(dest == p or str(dest).startswith(str(p) + "/") for p in allowed_prefixes)
    if not ok:
        raise RuntimeError(f"Refusing to write outside allowed paths: {dest_rel}")


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--artifact-dir", required=True)
    ap.add_argument("--run-id", required=True)
    ap.add_argument("--issue", required=True)
    ap.add_argument("--base-branch", default="main")
    ap.add_argument("--dry-run", default="true")
    args = ap.parse_args()

    artifact_dir = Path(args.artifact_dir).resolve()
    if not artifact_dir.exists():
        raise SystemExit(f"artifact-dir not found: {artifact_dir}")

    dry_run = str(args.dry_run).lower() in ("1", "true", "yes", "y")

    # Normalize artifact contents:
    # Accept either:
    #  - issue_1.md / request.json / response.json at root
    #  - .ai/dev/issue_1.md etc
    expected_issue_md = f"issue_{args.issue}.md"

    # Locate files
    candidates_issue = [
        artifact_dir / expected_issue_md,
        artifact_dir / ".ai" / "dev" / expected_issue_md,
    ]
    issue_path = next((p for p in candidates_issue if p.exists()), None)
    if issue_path is None:
        tree = "\n".join(sorted(str(p.relative_to(artifact_dir)) for p in artifact_dir.rglob("*")))
        raise SystemExit(f"Missing {expected_issue_md} in artifact.\nArtifact tree:\n{tree}")

    candidates_req = [artifact_dir / "request.json", artifact_dir / ".ai" / "dev" / "request.json"]
    req_path = next((p for p in candidates_req if p.exists()), None)

    candidates_resp = [artifact_dir / "response.json", artifact_dir / ".ai" / "dev" / "response.json"]
    resp_path = next((p for p in candidates_resp if p.exists()), None)

    # Prepare repo destination
    dest_dir = Path(".ai") / "dev"
    dest_dir.mkdir(parents=True, exist_ok=True)

    dest_issue = dest_dir / expected_issue_md
    ensure_clean_paths(dest_issue)
    shutil.copyfile(issue_path, dest_issue)

    if req_path is not None:
        dest_req = dest_dir / "request.json"
        ensure_clean_paths(dest_req)
        shutil.copyfile(req_path, dest_req)

    if resp_path is not None:
        dest_resp = dest_dir / "response.json"
        ensure_clean_paths(dest_resp)
        shutil.copyfile(resp_path, dest_resp)

    # Write apply digest (traceability)
    out_dir = Path("output")
    out_dir.mkdir(parents=True, exist_ok=True)
    dest_digest = out_dir / "apply_digest.txt"
    ensure_clean_paths(dest_digest)

    digest_value = f"run_id={args.run_id} issue={args.issue}"
    dest_digest.write_text(digest_value + "\n", encoding="utf-8")

    print(f"OK: normalized + staged files. dry_run={dry_run}")

    if dry_run:
        print("Dry-run: stopping before git commit/PR.")
        return

    # Git apply: create branch, commit, push
    base = args.base_branch
    branch = f"ai-live/issue-{args.issue}-run-{args.run_id}"

    sh(["git", "checkout", base])
    sh(["git", "pull", "--ff-only", "origin", base])
    sh(["git", "checkout", "-B", branch])

    sh(["git", "add", str(dest_issue), str(out_dir / "apply_digest.txt")])
    if req_path is not None:
        sh(["git", "add", str(dest_dir / "request.json")])
    if resp_path is not None:
        sh(["git", "add", str(dest_dir / "response.json")])

    # Commit only if there are changes
    status = sh(["git", "status", "--porcelain"])
    if status.strip() == "":
        print("No changes to commit.")
    else:
        msg = f"apply-live: issue #{args.issue} from run {args.run_id}"
        sh(["git", "commit", "-m", msg])

    sh(["git", "push", "--force-with-lease", "origin", branch])

    # Open PR
    token = os.environ.get("GH_TOKEN") or os.environ.get("GITHUB_TOKEN")
    if not token:
        raise SystemExit("Missing GH_TOKEN/GITHUB_TOKEN in env")

    owner = os.environ.get("OWNER")
    repo = os.environ.get("REPO")
    if not owner or not repo:
        raise SystemExit("Missing OWNER/REPO env")

    title = f"ai-live: issue #{args.issue} (run {args.run_id})"
    body = f"Apply LIVE DEV artifact 'live-dev' from workflow run {args.run_id}.\n\nTrace: output/apply_digest.txt"
    pr = create_pull_request(
        owner=owner,
        repo=repo,
        token=token,
        title=title,
        head=branch,
        base=base,
        body=body,
    )
    pr_url = pr.get("html_url", "")
    print(f"PR: {pr_url}")

    # Comment back to issue
    comment_issue(
        owner=owner,
        repo=repo,
        token=token,
        issue=str(args.issue),
        body=f"Opened PR: {pr_url}",
    )


if __name__ == "__main__":
    main()
