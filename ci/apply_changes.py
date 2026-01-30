import json, sys
from pathlib import Path

changes_path = sys.argv[1]
data = json.load(open(changes_path, "r", encoding="utf-8"))

changes = data.get("changes", [])
if not isinstance(changes, list):
    raise SystemExit("Invalid changes format")

for ch in changes:
    path = ch["path"]
    action = ch["action"]
    content = ch.get("content", "")

    p = Path(path)
    if action == "delete":
        if p.exists():
            p.unlink()
        continue

    if action in ("add", "edit"):
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(content, encoding="utf-8")
    else:
        raise SystemExit(f"Unknown action: {action}")

print(f"Applied {len(changes)} changes")
