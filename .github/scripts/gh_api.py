#!/usr/bin/env python3
"""
Minimal GitHub API helper for GitHub Actions.

Responsibilities:
- authenticated GitHub REST requests
- create PR
- post issue comment

NO side effects on import.
"""

import json
import os
import sys
import urllib.request
import urllib.error


class GitHubAPIError(RuntimeError):
    pass


def _require_env(name: str) -> str:
    val = os.getenv(name)
    if not val:
        raise GitHubAPIError(f"Missing required env var: {name}")
    return val


def _request(method: str, url: str, payload: dict | None = None) -> dict | None:
    token = _require_env("GITHUB_TOKEN")

    data = None
    if payload is not None:
        data = json.dumps(payload).encode("utf-8")

    req = urllib.request.Request(
        url=url,
        method=method,
        data=data,
        headers={
            "Authorization": f"Bearer {token}",
            "Accept": "application/vnd.github+json",
            "Content-Type": "application/json",
            "User-Agent": "media-transform-engine/gh_api",
        },
    )

    try:
        with urllib.request.urlopen(req) as resp:
            if resp.status in (200, 201):
                body = resp.read()
                return json.loads(body) if body else None
            if resp.status == 204:
                return None
            raise GitHubAPIError(f"Unexpected status {resp.status}")
    except urllib.error.HTTPError as e:
        body = e.read().decode("utf-8", errors="ignore")
        raise GitHubAPIError(f"GitHub API error {e.code}: {body}") from None


# ---------- Public API ----------


def create_pull_request(
    owner: str,
    repo: str,
    head: str,
    base: str,
    title: str,
    body: str,
) -> str:
    """
    Create PR and return PR URL.
    """
    url = f"https://api.github.com/repos/{owner}/{repo}/pulls"
    resp = _request(
        "POST",
        url,
        {
            "title": title,
            "head": head,
            "base": base,
            "body": body,
        },
    )
    if not resp or "html_url" not in resp:
        raise GitHubAPIError("PR creation failed: no html_url in response")
    return resp["html_url"]


def comment_issue(
    owner: str,
    repo: str,
    issue_number: int,
    body: str,
) -> None:
    """
    Post comment to issue or PR.
    """
    url = f"https://api.github.com/repos/{owner}/{repo}/issues/{issue_number}/comments"
    _request(
        "POST",
        url,
        {"body": body},
    )


# ---------- CLI (optional) ----------

if __name__ == "__main__":
    print("gh_api.py is a library, not a standalone script", file=sys.stderr)
    sys.exit(1)
