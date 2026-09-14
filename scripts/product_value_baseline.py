"""Validate or lock a completed local product-value source-only packet."""
from __future__ import annotations

import argparse
import sys
from datetime import datetime
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from charitygraph.product_value_baseline import lock_source_only_baseline, validate_source_only_packet


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    subparsers = parser.add_subparsers(dest="command", required=True)
    validate_parser = subparsers.add_parser("validate", help="verify packet hashes and source-only tree")
    validate_parser.add_argument("packet_dir", type=Path)
    lock_parser = subparsers.add_parser("lock", help="lock all completed source-only answers exactly once")
    lock_parser.add_argument("packet_dir", type=Path)
    lock_parser.add_argument("--completed-at", required=True, help="timezone-aware ISO-8601 timestamp")
    args = parser.parse_args()
    if args.command == "validate":
        print(validate_source_only_packet(args.packet_dir))
        return 0
    timestamp = datetime.fromisoformat(args.completed_at.replace("Z", "+00:00"))
    print(lock_source_only_baseline(args.packet_dir, completed_at=timestamp))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
