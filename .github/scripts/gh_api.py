#!/usr/bin/env python3
from __future__ import annotations

import json
import os
import urllib.request
import urllib.error
from typing import Any, Dict, Optional


class GHAPIError(RuntimeError):
    pass


def _request(
    method: str,
    url: str,
    token: str,
    payload: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    headers = {
        "Authorization": f"Bearer {token}",
        "Accept": "application/vnd.github+json",
        "User-Agent": "media-transform-engine-ci",
    }
    data = None
    if payload is not None:
        data = json.dumps(payload).encode("utf-8")
        headers["Content-Type"] = "application/json"

    req = urllib.request.Request(url, data=data, headers=headers, method=method)
    try:
        with urllib.request.urlopen(req, timeout=60) as resp:
            body = resp.read().decode("utf-8") if resp.readable() else ""
            if body.strip() == "":
                return {}
            return json.loads(body)
    except urllib.error.HTTPError as e:
        msg = e.read().decode("utf-8", errors="replace")
        raise GHAPIError(f"GitHub API error {e.code} for {url}: {msg}") from e
    except urllib.error.URLError as e:
        raise GHAPIError(f"GitHub API connection error for {url}: {e}") from e


def create_pull_request(
    *,
    owner: str,
    repo: str,
    token: str,
    title: str,
    head: str,
    base: str,
    body: str,
) -> Dict[str, Any]:
    url = f"https://api.github.com/repos/{owner}/{repo}/pulls"
    payload = {
        "title": title,
        "head": head,
        "base": base,
        "body": body,
    }
    return _request("POST", url, token, payload)


def comment_issue(
    *,
    owner: str,
    repo: str,
    token: str,
    issue: str,
    body: str,
) -> Dict[str, Any]:
    url = f"https://api.github.com/repos/{owner}/{repo}/issues/{issue}/comments"
    payload = {"body": body}
    return _request("POST", url, token, payload)
