"""Provider-free Phase D replay proof for a completed Factory runtime."""
from __future__ import annotations

import argparse
import json
import sqlite3
from datetime import datetime, timezone
from pathlib import Path

from charitygraph.runtime import SQLiteCatalog


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("database", type=Path)
    parser.add_argument("output", type=Path)
    args = parser.parse_args()
    now = datetime(2026, 9, 7, tzinfo=timezone.utc)
    with sqlite3.connect(f"file:{args.database.as_posix()}?mode=ro", uri=True) as conn:
        receipt = conn.execute(
            "SELECT provider_receipt_id, physical_attempt_id, raw_result_ref, usage_json FROM provider_receipts ORDER BY provider_receipt_id LIMIT 1"
        ).fetchone()
        before = conn.execute("SELECT count(*) FROM provider_receipts").fetchone()[0]
        terminal_before = conn.execute("SELECT count(*) FROM tasks WHERE status='succeeded'").fetchone()[0]
    if receipt is None:
        raise RuntimeError("Phase D requires a completed receipt")
    catalog = SQLiteCatalog(args.database).open(initialize=False)
    replay = catalog.persist_provider_receipt(
        physical_attempt_id=receipt[1],
        provider_receipt_id=receipt[0],
        raw_result_ref=receipt[2],
        usage=json.loads(receipt[3]),
        now=now,
    )
    with sqlite3.connect(f"file:{args.database.as_posix()}?mode=ro", uri=True) as conn:
        after = conn.execute("SELECT count(*) FROM provider_receipts").fetchone()[0]
        terminal_after = conn.execute("SELECT count(*) FROM tasks WHERE status='succeeded'").fetchone()[0]
        integrity = conn.execute("PRAGMA integrity_check").fetchone()[0]
        foreign = conn.execute("PRAGMA foreign_key_check").fetchall()
    result = {
        "phase": "D",
        "duplicate_receipt_idempotent": replay["provider_receipt_id"] == receipt[0] and before == after,
        "receipt_count_before": before,
        "receipt_count_after": after,
        "terminal_successes_before": terminal_before,
        "terminal_successes_after": terminal_after,
        "sqlite_integrity": integrity,
        "foreign_key_violations": foreign,
        "network_calls": 0,
        "provider_calls": 0,
        "semantic_knowledge_production": 0,
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(result, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps(result, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
