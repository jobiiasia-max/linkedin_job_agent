import json
from datetime import datetime
from pathlib import Path


def log(msg):
    print(f"[{datetime.now():%Y-%m-%d %H:%M:%S}] {msg}", flush=True)


def load_seen(path):
    p = Path(path)
    if p.exists():
        try:
            return json.loads(p.read_text())
        except json.JSONDecodeError:
            pass
    return {}


def save_seen(path, seen):
    Path(path).write_text(json.dumps(seen, indent=2))
