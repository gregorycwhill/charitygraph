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
from charitygraph.phase5_standard_transport import OpenAIHTTPStandardClient
from charitygraph.s0_live import canonical_locator_provider_factory
from charitygraph.s0_live_preparation import HumanA3Input, persist_explicit_a3, prepare_locator_lifecycle
from charitygraph.s0_pricing import load_supervisor_capture
from charitygraph.scale_s0 import ExecutionAttemptIdentity, FrozenPacket
from datetime import datetime, timezone


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
    parser.add_argument("--pricing-capture", type=Path)
    parser.add_argument("--pricing-capture-sha256")
    parser.add_argument("--cohort-id")
    parser.add_argument("--attested-by")
    parser.add_argument("--observed-at")
    parser.add_argument("--setting-name")
    parser.add_argument("--observed-value")
    parser.add_argument("--provider-project")
    parser.add_argument("--execution-authority")
    args = parser.parse_args()
    material = json.loads(args.work.read_text(encoding="utf-8"))
    semantic = tuple(S0SemanticWork(str(item["packet_id"]), dict(item["row"]), _request(item["request"])) for item in material.get("semantic", ()))
    locator = tuple(S0LocatorWork(str(item["packet_id"]), _request(item["request"]), str(item["delivery_attempt_id"]), str(item["client_request_id"]), str(item["query"])) for item in material.get("locator", ()))
    with SQLiteCatalog(args.catalog).open() as catalog:
        snapshot = None
        if args.pricing_capture or args.pricing_capture_sha256:
            if not args.pricing_capture or not args.pricing_capture_sha256:
                raise SystemExit("pricing capture path and SHA-256 are both required")
            snapshot = load_supervisor_capture(args.pricing_capture, expected_sha256=args.pricing_capture_sha256)
        provider = None
        factory = None
        if not args.preflight:
            required = (args.cohort_id, args.attested_by, args.observed_at, args.setting_name, args.observed_value, args.provider_project, args.execution_authority, snapshot)
            if any(value is None for value in required):
                raise SystemExit("live execution requires explicit cohort, A3 fields, project, authority, and pricing capture")
            row = catalog.get_scale_s0_execution_attempt(args.attempt_id)
            if row is None:
                raise SystemExit("durable execution attempt is absent")
            attempt = ExecutionAttemptIdentity(**{name: row["material"][name] for name in ExecutionAttemptIdentity.__dataclass_fields__})
            observed = datetime.fromisoformat(args.observed_at)
            window = persist_explicit_a3(catalog, attempt=attempt, attestation=HumanA3Input(args.attested_by, observed, args.setting_name, args.observed_value, args.provider_project, args.execution_authority), now=datetime.now(timezone.utc))
            for item in locator:
                stored = catalog.get_scale_s0_frozen_packet(item.packet_id)
                packet = FrozenPacket(**{name: stored["material"][name] for name in FrozenPacket.__dataclass_fields__ if name in stored["material"]})
                prepared = prepare_locator_lifecycle(catalog=catalog, attempt=attempt, packet=packet, request=item.request, cohort_id=args.cohort_id, now=datetime.now(timezone.utc), attestation_window=window)
                if prepared["delivery_attempt_id"] != item.delivery_attempt_id:
                    raise SystemExit("work delivery attempt identity does not match canonical preparation")
            client = OpenAIHTTPStandardClient(provider_account_project=args.provider_project)
            factory = canonical_locator_provider_factory(client=client)
        summary = ScaleS0Executor(catalog=catalog, attempt_id=args.attempt_id, builder_commit_sha=args.builder_commit_sha, runtime_root=args.runtime_root, locator_provider_factory=factory, pricing_snapshot=snapshot).run(semantic=semantic, locator=locator, dry_run=args.preflight)
    print(summary_json(summary))
    return 0 if not summary.stop_campaign or summary.preflight else 2


if __name__ == "__main__":
    raise SystemExit(main())
