#!/usr/bin/env python3
import argparse
import json
import os
from decimal import Decimal, InvalidOperation
from pathlib import Path

EXIT_CONFIG_MISSING = 3
EXIT_CONFIG_INVALID = 4
EXIT_BUDGET_EXCEEDED = 5

def die(msg: str, code: int) -> None:
    print(msg, flush=True)
    raise SystemExit(code)

def load_json(path: Path) -> dict:
    try:
        with path.open("r", encoding="utf-8") as f:
            return json.load(f)
    except FileNotFoundError:
        die(f"Missing file: {path}", EXIT_CONFIG_MISSING)
    except Exception as e:
        die(f"Invalid JSON in {path}: {e}", EXIT_CONFIG_INVALID)

def as_decimal(s: str, field: str) -> Decimal:
    try:
        return Decimal(s)
    except (InvalidOperation, ValueError):
        die(f"Invalid decimal for {field}: {s}", EXIT_CONFIG_INVALID)

def as_int(s: str, field: str) -> int:
    try:
        return int(s)
    except Exception:
        die(f"Invalid int for {field}: {s}", EXIT_CONFIG_INVALID)

def validate_config(cfg: dict, max_out_tok: int) -> dict:
    roles = cfg.get("roles")
    if not isinstance(roles, dict):
        die("Config missing top-level key: roles", EXIT_CONFIG_INVALID)

    out = {}
    for role in ("arch", "dev", "qa"):
        if role not in roles:
            die(f"Config missing role: {role}", EXIT_CONFIG_INVALID)
        r = roles[role]
        for k in ("model", "price_in_per_1k", "price_out_per_1k", "max_output_tokens"):
            if k not in r:
                die(f"Config role {role} missing key: {k}", EXIT_CONFIG_INVALID)

        price_in = as_decimal(str(r["price_in_per_1k"]), f"{role}.price_in_per_1k")
        price_out = as_decimal(str(r["price_out_per_1k"]), f"{role}.price_out_per_1k")
        max_out = as_int(str(r["max_output_tokens"]), f"{role}.max_output_tokens")

        if max_out > max_out_tok:
            die(
                f"Config role {role} max_output_tokens exceeds cap: {max_out} > {max_out_tok}",
                EXIT_CONFIG_INVALID,
            )

        out[role] = {"price_in": price_in, "price_out": price_out, "max_out": max_out}
    return out

def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--cfg", required=True)
    ap.add_argument("--issue_json", required=True)
    ap.add_argument("--comments_json", required=True)
    ap.add_argument("--max_out_tok", required=True)
    ap.add_argument("--max_in_tok", required=True)
    ap.add_argument("--max_usd", required=True)
    ap.add_argument("--fail_on", required=True)  # "true"/"false"
    ap.add_argument("--out_dir", required=True)
    args = ap.parse_args()

    cfg_path = Path(args.cfg)
    issue_path = Path(args.issue_json)
    comments_path = Path(args.comments_json)
    out_dir = Path(args.out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)

    max_out_tok = as_int(args.max_out_tok, "max_out_tok")
    max_in_tok = as_int(args.max_in_tok, "max_in_tok")
    max_usd = as_decimal(args.max_usd, "max_usd")
    fail_on = args.fail_on.strip().lower()
    if fail_on not in ("true", "false"):
        die(f"Invalid fail_on: {args.fail_on}", EXIT_CONFIG_INVALID)

    cfg = load_json(cfg_path)
    roles = validate_config(cfg, max_out_tok)

    # Conservative token estimate: bytes/3 + overhead per call; worst-case 3 calls
    issue_bytes = issue_path.stat().st_size
    comments_bytes = comments_path.stat().st_size
    total_bytes = issue_bytes + comments_bytes

    est_in_tok_per_call = total_bytes // 3 + 800
    est_total_in_tok = est_in_tok_per_call * 3

    def role_cost(role_name: str) -> Decimal:
        r = roles[role_name]
        return (Decimal(est_in_tok_per_call) / Decimal(1000)) * r["price_in"] + (
            Decimal(r["max_out"]) / Decimal(1000)
        ) * r["price_out"]

    est_total_usd = role_cost("arch") + role_cost("dev") + role_cost("qa")

    # Write budget.txt (single value) for easy reading
    (out_dir / "budget.txt").write_text(f"{est_total_usd:.6f}\n", encoding="utf-8")

    # Write live_gate.txt summary (machine-readable)
    live_gate = "\n".join(
        [
            "run_live_effective=true",
            f"issue_bytes={issue_bytes}",
            f"comments_bytes={comments_bytes}",
            f"total_bytes={total_bytes}",
            f"est_input_tokens_per_call={est_in_tok_per_call}",
            f"est_total_input_tokens={est_total_in_tok}",
            f"max_input_tokens={max_in_tok}",
            f"est_total_usd={est_total_usd:.6f}",
            f"max_usd={max_usd}",
            f"fail_on_budget_exceed={fail_on}",
        ]
    )
    (out_dir / "live_gate.txt").write_text(live_gate + "\n", encoding="utf-8")

    exceed = False
    if est_total_in_tok > max_in_tok:
        exceed = True
        print(
            f"Budget fail: est_total_input_tokens ({est_total_in_tok}) > max_input_tokens ({max_in_tok})",
            flush=True,
        )
    if est_total_usd > max_usd:
        exceed = True
        print(
            f"Budget fail: est_total_usd ({est_total_usd:.6f}) > max_usd ({max_usd})",
            flush=True,
        )

    if exceed and fail_on == "true":
        die("Fail-fast: LIVE budgets exceeded. No OpenAI calls executed.", EXIT_BUDGET_EXCEEDED)

    return 0

if __name__ == "__main__":
    raise SystemExit(main())
