#!/usr/bin/env python3
from __future__ import annotations

import json
import os
import urllib.request
import urllib.error


def _headers(token: str) -> dict[str, str]:
    return {
        "Authorization": f"Bearer {token}",
        "Accept": "application/vnd.github+json",
        "Content-Type": "application/json",
        "User-Agent": "media-transform-engine-ci",
    }


def request_json(method: str, url: str, token: str, payload: dict | None = None) -> tuple[int, dict | None, str]:
    data = None
    if payload is not None:
        data = json.dumps(payload).encode("utf-8")

    req = urllib.request.Request(url, method=method, headers=_headers(token), data=data)
    try:
        with urllib.request.urlopen(req) as resp:
            body = resp.read().decode("utf-8", errors="replace")
            if body.strip():
                try:
                    return resp.status, json.loads(body), body
                except json.JSONDecodeError:
                    return resp.status, None, body
            return resp.status, None, ""
    except urllib.error.HTTPError as e:
        body = e.read().decode("utf-8", errors="replace")
        parsed = None
        if body.strip():
            try:
                parsed = json.loads(body)
            except json.JSONDecodeError:
                parsed = None
        return e.code, parsed, body
