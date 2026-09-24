"""Fail-closed CLI for one catalog-bound Scale S0 execution.

The JSON input contains only already-prepared lifecycle rows and request
fields.  This command never registers authority or creates an attempt.
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path

from charitygraph.runtime import SQLiteCatalog
from charitygraph.scale_s0 import RoutingClass, SendRequest
from charitygraph.s0_orchestration import ScaleS0Executor, S0LocatorWork, S0SemanticWork, summary_json


def _request(value: dict) -> SendRequest:
    fields = {name: value[name] for name in SendRequest.__dataclass_fields__ if name in value}
    fields["route"] = RoutingClass(str(fields["route"]))
    fields["source_ids"] = tuple(fields.get("source_ids") or ())
    return SendRequest(**fields)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--catalog", required=True, type=Path)
    parser.add_argument("--attempt-id", required=True)
    parser.add_argument("--builder-commit-sha", required=True)
    parser.add_argument("--runtime-root", required=True, type=Path)
    parser.add_argument("--work", required=True, type=Path, help="JSON with semantic and locator arrays")
    parser.add_argument("--preflight", action="store_true", help="reconstruct and validate without a provider")
    args = parser.parse_args()
    material = json.loads(args.work.read_text(encoding="utf-8"))
    semantic = tuple(S0SemanticWork(str(item["packet_id"]), dict(item["row"]), _request(item["request"])) for item in material.get("semantic", ()))
    locator = tuple(S0LocatorWork(str(item["packet_id"]), _request(item["request"]), str(item["delivery_attempt_id"]), str(item["client_request_id"]), str(item["query"])) for item in material.get("locator", ()))
    with SQLiteCatalog(args.catalog).open() as catalog:
        summary = ScaleS0Executor(catalog=catalog, attempt_id=args.attempt_id, builder_commit_sha=args.builder_commit_sha, runtime_root=args.runtime_root).run(semantic=semantic, locator=locator, dry_run=args.preflight)
    print(summary_json(summary))
    return 0 if not summary.stop_campaign or summary.preflight else 2


if __name__ == "__main__":
    raise SystemExit(main())
