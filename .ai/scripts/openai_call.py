#!/usr/bin/env python3
import argparse
import json
import os
import sys
import urllib.request
import urllib.error
from pathlib import Path

API_URL = "https://api.openai.com/v1/responses"

def die(msg: str, code: int = 1) -> None:
    print(msg, file=sys.stderr, flush=True)
    raise SystemExit(code)

def extract_text(resp: dict) -> str:
    # Prefer convenience field if present
    if isinstance(resp, dict) and isinstance(resp.get("output_text"), str) and resp["output_text"].strip():
        return resp["output_text"]

    # Fallback: traverse output -> content -> text
    out = resp.get("output")
    if isinstance(out, list):
        chunks = []
        for item in out:
            content = item.get("content") if isinstance(item, dict) else None
            if isinstance(content, list):
                for c in content:
                    if isinstance(c, dict) and c.get("type") == "output_text":
                        t = c.get("text")
                        if isinstance(t, str):
                            chunks.append(t)
                    elif isinstance(c, dict) and "text" in c and isinstance(c["text"], str):
                        chunks.append(c["text"])
        text = "\n".join([x for x in chunks if x.strip()])
        if text.strip():
            return text

    return ""

def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--model", required=True)
    ap.add_argument("--max_output_tokens", required=True, type=int)
    ap.add_argument("--system", required=True)
    ap.add_argument("--user", required=True)
    ap.add_argument("--out_dir", required=True)
    args = ap.parse_args()

    key = os.environ.get("OPENAI_API_KEY", "").strip()
    if not key:
        die("OPENAI_API_KEY is missing (set as GitHub Actions secret).", 2)

    out_dir = Path(args.out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)

    payload = {
        "model": args.model,
        "input": [
            {
                "role": "system",
                "content": [{"type": "text", "text": args.system}],
            },
            {
                "role": "user",
                "content": [{"type": "text", "text": args.user}],
            },
        ],
        "max_output_tokens": int(args.max_output_tokens),
        "temperature": 0,
        "store": False,
    }

    data = json.dumps(payload).encode("utf-8")
    req = urllib.request.Request(
        API_URL,
        data=data,
        headers={
            "Authorization": f"Bearer {key}",
            "Content-Type": "application/json",
        },
        method="POST",
    )

    try:
        with urllib.request.urlopen(req, timeout=120) as r:
            raw = r.read().decode("utf-8", errors="replace")
    except urllib.error.HTTPError as e:
        body = e.read().decode("utf-8", errors="replace") if e.fp else ""
        die(f"OpenAI HTTPError {e.code}: {body}", 3)
    except Exception as e:
        die(f"OpenAI request failed: {e}", 4)

    try:
        resp = json.loads(raw)
    except Exception as e:
        die(f"Invalid JSON from OpenAI: {e}\nRAW:\n{raw}", 5)

    (out_dir / "response.json").write_text(json.dumps(resp, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    text = extract_text(resp)
    if not text.strip():
        # Still keep response.json for debugging
        die("OpenAI response contained no extractable text (see response.json).", 6)

    (out_dir / "arch.md").write_text(text.strip() + "\n", encoding="utf-8")
    return 0

if __name__ == "__main__":
    raise SystemExit(main())
