from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
AUDIT_DIR = ROOT / "data" / "audit"
AUDIT_FILE = AUDIT_DIR / "audit.jsonl"


def log_event(record: dict) -> dict:
    AUDIT_DIR.mkdir(parents=True, exist_ok=True)
    stamped = {
        "ts": datetime.now(timezone.utc).isoformat(),
        "airgap": True,
        "egress": "blocked-by-design",
        **record,
    }
    with AUDIT_FILE.open("a", encoding="utf-8") as fh:
        fh.write(json.dumps(stamped, ensure_ascii=False) + "\n")
    return stamped


def recent(limit: int = 40) -> list[dict]:
    if not AUDIT_FILE.exists():
        return []
    lines = AUDIT_FILE.read_text(encoding="utf-8").splitlines()
    rows = []
    for line in lines[-limit:]:
        try:
            rows.append(json.loads(line))
        except json.JSONDecodeError:
            continue
    rows.reverse()
    return rows
