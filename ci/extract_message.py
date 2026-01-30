import json, sys

raw_path = sys.argv[1]
out_path = sys.argv[2]

data = json.load(open(raw_path, "r", encoding="utf-8"))

content = None
try:
    content = data["choices"][0]["message"]["content"]
except Exception:
    content = data.get("output_text")

if not content or not isinstance(content, str):
    raise SystemExit("Could not extract model content")

open(out_path, "w", encoding="utf-8").write(content)
