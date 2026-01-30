#!/usr/bin/env python3
import argparse
import json
import sys
from pathlib import Path

def die(msg: str, code: int = 1) -> None:
    print(msg, file=sys.stderr, flush=True)
    raise SystemExit(code)

def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--cfg", required=True)
    ap.add_argument("--role", required=True, choices=["arch", "dev", "qa"])
    ap.add_argument("--field", required=True, choices=["model", "max_output_tokens"])
    args = ap.parse_args()

    p = Path(args.cfg)
    if not p.exists():
        die(f"Missing config: {p}", 2)

    try:
        cfg = json.loads(p.read_text(encoding="utf-8"))
    except Exception as e:
        die(f"Invalid JSON in {p}: {e}", 3)

    roles = cfg.get("roles")
    if not isinstance(roles, dict):
        die("Config missing top-level key: roles", 4)

    r = roles.get(args.role)
    if not isinstance(r, dict):
        die(f"Config missing role: {args.role}", 5)

    if args.field not in r:
        die(f"Config role {args.role} missing key: {args.field}", 6)

    v = r[args.field]
    if args.field == "max_output_tokens":
        try:
            v = int(v)
        except Exception:
            die(f"Invalid int for {args.role}.max_output_tokens: {v}", 7)

    print(v)
    return 0

if __name__ == "__main__":
    raise SystemExit(main())
