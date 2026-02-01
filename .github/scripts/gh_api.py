#!/usr/bin/env python3
import argparse
import json
import os
import sys
import urllib.request
import urllib.error
import zipfile
from typing import Any, Dict, List, Optional


API = "https://api.github.com"


def die(msg: str, code: int = 2) -> None:
    print(f"ERROR: {msg}", file=sys.stderr)
    sys.exit(code)


def gh_token() -> str:
    t = os.environ.get("GH_TOKEN") or os.environ.get("GITHUB_TOKEN")
    if not t:
        die("GH_TOKEN (or GITHUB_TOKEN) is required in env", 3)
    return t


def request_json(url: str) -> Any:
    req = urllib.request.Request(url)
    req.add_header("Authorization", f"Bearer {gh_token()}")
    req.add_header("Accept", "application/vnd.github+json")
    try:
        with urllib.request.urlopen(req, timeout=60) as r:
            data = r.read().decode("utf-8")
            return json.loads(data)
    except urllib.error.HTTPError as e:
        body = e.read().decode("utf-8", errors="replace") if hasattr(e, "read") else ""
        die(f"HTTP {e.code} for {url}\n{body}", 10)


def download_to(url: str, out_path: str) -> None:
    req = urllib.request.Request(url)
    req.add_header("Authorization", f"Bearer {gh_token()}")
    req.add_header("Accept", "application/vnd.github+json")

    # GitHub returns 302 to blob storage; urllib follows redirects.
    try:
        with urllib.request.urlopen(req, timeout=120) as r, open(out_path, "wb") as f:
            while True:
                chunk = r.read(1024 * 1024)
                if not chunk:
                    break
                f.write(chunk)
    except urllib.error.HTTPError as e:
        body = e.read().decode("utf-8", errors="replace") if hasattr(e, "read") else ""
        die(f"Download failed HTTP {e.code} for {url}\n{body}", 11)


def list_run_artifacts(owner: str, repo: str, run_id: str) -> List[Dict[str, Any]]:
    url = f"{API}/repos/{owner}/{repo}/actions/runs/{run_id}/artifacts?per_page=100"
    data = request_json(url)
    arts = data.get("artifacts", [])
    if not isinstance(arts, list):
        die("Unexpected artifacts payload", 12)
    return arts


def pick_artifact(artifacts: List[Dict[str, Any]], name: str) -> Optional[Dict[str, Any]]:
    # prefer exact name
    exact = [a for a in artifacts if str(a.get("name", "")) == name]
    if exact:
        return sorted(exact, key=lambda x: int(x.get("id", 0)), reverse=True)[0]

    # then prefix match
    pref = [a for a in artifacts if str(a.get("name", "")).startswith(name)]
    if pref:
        return sorted(pref, key=lambda x: int(x.get("id", 0)), reverse=True)[0]

    # then contains match
    cont = [a for a in artifacts if name in str(a.get("name", ""))]
    if cont:
        return sorted(cont, key=lambda x: int(x.get("id", 0)), reverse=True)[0]

    return None


def cmd_list(args: argparse.Namespace) -> None:
    arts = list_run_artifacts(args.owner, args.repo, args.run_id)
    for a in arts:
        print(f"{a.get('name','')} id={a.get('id','')} size_in_bytes={a.get('size_in_bytes','')}")


def cmd_download(args: argparse.Namespace) -> None:
    arts = list_run_artifacts(args.owner, args.repo, args.run_id)
    if not arts:
        die(f"No artifacts found in run {args.run_id}", 20)

    art = pick_artifact(arts, args.name)
    if not art:
        names = ", ".join(sorted({str(a.get("name", "")) for a in arts}))
        die(f"Artifact '{args.name}' not found in run {args.run_id}. Found: {names}", 21)

    dl_url = art.get("archive_download_url")
    if not dl_url:
        die("archive_download_url missing", 22)

    out_dir = args.out_dir
    os.makedirs(out_dir, exist_ok=True)
    zip_path = os.path.join(out_dir, "_artifact.zip")

    print(f"Downloading artifact: name={art.get('name')} id={art.get('id')} -> {zip_path}")
    download_to(dl_url, zip_path)

    # Extract
    with zipfile.ZipFile(zip_path, "r") as z:
        z.extractall(out_dir)

    os.remove(zip_path)
    print(f"Extracted into: {out_dir}")


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(prog="gh_api.py")
    sub = p.add_subparsers(dest="cmd", required=True)

    p_list = sub.add_parser("list-artifacts", help="List artifacts for a workflow run")
    p_list.add_argument("--owner", required=True)
    p_list.add_argument("--repo", required=True)
    p_list.add_argument("--run-id", required=True)
    p_list.set_defaults(func=cmd_list)

    p_dl = sub.add_parser("download-artifact", help="Download + unzip artifact from a run (by name, robust match)")
    p_dl.add_argument("--owner", required=True)
    p_dl.add_argument("--repo", required=True)
    p_dl.add_argument("--run-id", required=True)
    p_dl.add_argument("--name", required=True)
    p_dl.add_argument("--out-dir", required=True)
    p_dl.set_defaults(func=cmd_download)

    return p


def main() -> None:
    parser = build_parser()
    args = parser.parse_args()
    # normalize attribute for handlers
    if hasattr(args, "run_id"):
        args.run_id = str(args.run_id)
    args.func(args)


if __name__ == "__main__":
    main()
