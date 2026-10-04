"""End-to-end provider-free rehearsal through the canonical S0 CLI."""
from __future__ import annotations

import hashlib
import json
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest

from charitygraph.runtime import SQLiteCatalog
from charitygraph.runtime.catalog import canonical_execution_configuration_hash
from charitygraph.s0_locator_discovery import freeze_locator_search_packet, prepare_locator_search_request
from charitygraph.s0_live_preparation import checkpoint_structured_locator_preprovider
from charitygraph.s0_structured_authority import (
    FrozenLocatorQueries, GovernedLocatorBinding, LocatorAuthorityMaterial,
    frozen_locator_material_sha256,
)
from charitygraph.scale_s0 import ExecutionAttemptIdentity, ScaleS0Preflight
from charitygraph.scale_s0 import ScalePreflightError
from charitygraph.scale_s0 import locator_search_request_body_sha256
from charitygraph.s0_pricing import load_supervisor_capture
from scripts.run_scale_s0 import main

from .test_s0_locator_search_lifecycle import _authority, _attempt, NOW, PROJECT


def _write_rehearsal_pricing_capture(path: Path) -> tuple[Path, str]:
    """Create a governed fixture locally; tests must not depend on Drive residue."""
    capture = {
        "schema": "charitygraph-supervisor-pricing-capture-v1",
        "provenance_note": "test fixture, not over raw upstream HTML",
        "model": "gpt-5.6-luna",
        "currency": "USD",
        "captured_at": "2026-10-03T00:00:00+00:00",
        "model_pricing": {
            "input_usd_per_million_tokens": "0.25",
            "cached_input_usd_per_million_tokens": "0.025",
            "output_usd_per_million_tokens": "2.00",
        },
        "web_search_pricing": {
            "search_content_tokens_billed_at_model_rates": True,
            "usd_per_1000_calls": "10.00",
        },
    }
    raw = json.dumps(capture, sort_keys=True, separators=(",", ":")).encode("utf-8")
    path.write_bytes(raw)
    return path, hashlib.sha256(raw).hexdigest()


class FakeResponse:
    status = 200
    headers = {"x-request-id": "server-rehearsal"}

    def __init__(self, body):
        self._raw = json.dumps(body, sort_keys=True, separators=(",", ":")).encode()

    def __enter__(self): return self
    def __exit__(self, *_): return None
    def read(self): return self._raw


def _make_catalog(path: Path, subjects: tuple[str, ...], pricing_id: str):
    mandate, registry, routing, policies = _authority()
    attempt = _attempt(mandate)
    catalog = SQLiteCatalog(path).open(initialize=True)
    ScaleS0Preflight.register_durable_mandate(catalog, mandate, registry, routing, policies, {})
    membership = __import__("hashlib").sha256(json.dumps(mandate.subject_ids, separators=(",", ":")).encode()).hexdigest()
    catalog.register_cohort({"record_id": "cohort:locator", "cohort_code": "LOCATOR", "definition_version": "1", "membership_hash": membership, "budget_cap": {"amount": "8.00", "currency": "USD"}, "created_at": NOW})
    catalog.register_run({"record_id": attempt.run_id, "cohort_id": "cohort:locator", "run_kind": "s0", "status": "planned", "configuration_hash": attempt.configuration_hash, "created_at": NOW})
    ScaleS0Preflight.register_durable_execution_attempt(catalog, attempt)
    work = []
    for index, subject in enumerate(subjects):
        packet = freeze_locator_search_packet(mandate=mandate, execution_attempt=attempt, locator_subject_ref=subject, locator_abn="11111111111", query=f'"Locator {subject} {index}"', query_index=index,
                                               pricing=__import__("charitygraph.s0_locator_discovery", fromlist=["LocatorSearchPrice"]).LocatorSearchPrice(pricing_id, "0.10", "USD"), frozen_at=NOW.isoformat(),
                                               provider_account_project=PROJECT, execution_authority="authority:rehearsal")
        ScaleS0Preflight.register_durable_packet(catalog, mandate, packet, execution_attempt_id=attempt.attempt_id)
        for bundle in __import__("charitygraph.s0_acquisition_bridge", fromlist=["bundle_packets"]).bundle_packets(mandate, (packet,), now=NOW, execution_attempt_id=attempt.attempt_id):
            catalog.register_scale_s0_physical_bundle(bundle.__dict__, execution_attempt_id=attempt.attempt_id)
        prepared = prepare_locator_search_request(packet=packet, reservation_id=f"reservation:rehearsal:{index}", provider_account_project=PROJECT, execution_authority="authority:rehearsal")
        request_material = {name: getattr(prepared.request, name) for name in prepared.request.__dataclass_fields__}
        request_material["route"] = request_material["route"].value
        work.append({"packet_id": packet.packet_id, "delivery_attempt_id": prepared.delivery_attempt_id, "client_request_id": prepared.client_request_id, "query": packet.locator_query, "request": request_material})
    catalog.close()
    return attempt, work


def test_live_cli_rejects_legacy_opaque_a3_rehearsal_before_provider_construction(tmp_path, monkeypatch):
    capture, capture_sha = _write_rehearsal_pricing_capture(tmp_path / "pricing.json")
    snapshot = load_supervisor_capture(capture, expected_sha256=capture_sha)
    db = tmp_path / "rehearsal.sqlite3"
    attempt, work = _make_catalog(db, ("subject:locator", "subject:locator", "subject:locator"), snapshot.record_id)
    work_path = tmp_path / "work.json"
    work_path.write_text(json.dumps({"locator": work}), encoding="utf-8")
    posts = []
    def fake_urlopen(request, **_kwargs):
        posts.append((request.get_method(), request.full_url, dict(request.header_items()), request.data))
        body = {"id": f"resp_{len(posts)}", "model": "gpt-5.6-luna", "status": "completed",
                "usage": {"input_tokens": 100, "output_tokens": 20, "input_tokens_details": {"cached_tokens": 10}},
                "output": [{"type": "web_search_call", "action": {"type": "search", "sources": [{"url": "https://example.org/"}]}}]}
        return FakeResponse(body)
    monkeypatch.setattr("charitygraph.phase5_standard_transport.urlopen", fake_urlopen)
    now = datetime.now(timezone.utc).isoformat()
    argv = ["--catalog", str(db), "--attempt-id", attempt.attempt_id, "--builder-commit-sha", "a" * 40, "--runtime-root", str(tmp_path), "--work", str(work_path),
            "--pricing-capture", str(capture), "--pricing-capture-sha256", capture_sha, "--cohort-id", "cohort:locator", "--attested-by", "Greg",
            "--observed-at", now, "--setting-name", "Share inputs and outputs with OpenAI", "--observed-value", "Disabled", "--provider-project", PROJECT, "--execution-authority", "authority:rehearsal"]
    # The legacy fixture deliberately has no structured checkpoint/material.
    # It must stop before constructing a client or emitting a provider POST.
    with pytest.raises(SystemExit, match="A3 fields"):
        main(argv)
    assert not posts


def test_structured_a3_preflight_reaches_provider_boundary_without_attestation_or_provider(tmp_path, monkeypatch):
    """The production CLI validates Attempt 21's whole pre-provider contract.

    This is intentionally a clean-room fixture: no pricing capture, provider
    client, A3 record, reservation, transport trace, or network call exists.
    """
    mandate, registry, routing, policies = _authority()
    policies = dict(policies)
    policies["population"] = __import__("dataclasses").replace(
        policies["sampling"], policy_id="population:clean-room", content_hash="e" * 64,
    )
    mandate = __import__("dataclasses").replace(
        mandate, mandate_id="scale-s0-authorised-balanced-v3", subject_ids=("74068758654",),
        policy_hashes={**mandate.policy_hashes, "population": policies["population"].content_hash},
    )
    attempt = _attempt(mandate)
    attempt = __import__("dataclasses").replace(
        attempt, attempt_id="attempt:s0:21", run_id="run:s0:attempt-21",
        mandate_id=mandate.mandate_id, mandate_hash=mandate.identity_hash,
        builder_commit_sha="a" * 40, data_commit_sha="b" * 40,
    )
    attempt = __import__("dataclasses").replace(attempt, configuration_hash=canonical_execution_configuration_hash(**{
        key: getattr(attempt, key) for key in (
            "mandate_hash", "slice_id", "run_id", "builder_repository", "builder_commit_sha",
            "data_repository", "data_commit_sha", "bridge_certification", "bridge_version",
            "schema_version", "recovery_authority_ref",
        )
    }))
    binding = GovernedLocatorBinding("locator-subject:v1:sha256:" + "c" * 64, "ABN", "74068758654")
    frozen = (FrozenLocatorQueries(binding, ('"Clean Room Foundation" "74068758654"',)),)
    policy_rows = [{"key": key, "policy_id": value.policy_id, "version": value.version,
                    "hash": value.content_hash} for key, value in sorted(policies.items()) if key != "reservation"]
    aggregate_policy_hash = __import__("hashlib").sha256(
        json.dumps(policy_rows, sort_keys=True, separators=(",", ":")).encode("utf-8")).hexdigest().upper()
    authority = LocatorAuthorityMaterial(
        "CG-S0-PO-ATTEMPT21-CLEANROOM", attempt.attempt_id, attempt.run_id,
        attempt.builder_commit_sha, attempt.data_commit_sha, PROJECT,
        frozen_locator_material_sha256(frozen), (binding,), 1, "0.10", "0.10",
        mandate_id=mandate.mandate_id, mandate_hash=mandate.identity_hash,
        aggregate_policy_bundle_hash=aggregate_policy_hash, population_policy_hash=policies["population"].content_hash,
    )
    db = tmp_path / "clean-room.sqlite3"
    with SQLiteCatalog(db).open(initialize=True) as catalog:
        ScaleS0Preflight.register_durable_mandate(catalog, mandate, registry, routing, policies, {})
        catalog.register_run({"record_id": attempt.run_id, "run_kind": "s0", "status": "planned",
                              "configuration_hash": attempt.configuration_hash, "created_at": NOW})
        ScaleS0Preflight.register_durable_execution_attempt(catalog, attempt)
        initial = checkpoint_structured_locator_preprovider(catalog=catalog, attempt=attempt, authority=authority,
                                                            frozen_subjects=frozen, now=NOW)
        replayed = checkpoint_structured_locator_preprovider(catalog=catalog, attempt=attempt, authority=authority,
                                                             frozen_subjects=frozen, now=NOW + timedelta(minutes=5))
        assert replayed["material_hash"] == initial["material_hash"]
    authority_path = tmp_path / "attempt21-authority.json"
    authority_path.write_text(json.dumps(authority.material()), encoding="utf-8")
    work_path = tmp_path / "work.json"
    work_path.write_text('{"semantic": [], "locator": []}', encoding="utf-8")
    monkeypatch.setattr("charitygraph.phase5_standard_transport.urlopen", lambda *_a, **_k: pytest.fail("provider called"))
    argv = ["--catalog", str(db), "--attempt-id", attempt.attempt_id, "--builder-commit-sha", attempt.builder_commit_sha,
            "--runtime-root", str(tmp_path), "--work", str(work_path), "--preflight", "--cohort-id", "cohort:clean-room",
            "--attested-by", "Greg", "--observed-at", datetime.now(timezone.utc).isoformat(),
            "--setting-name", "Share inputs and outputs with OpenAI", "--observed-value", "Disabled",
            "--provider-project", PROJECT, "--execution-authority", authority.hash,
            "--structured-authority", str(authority_path), "--structured-authority-sha256", authority.hash]
    assert main(argv) == 0
    with SQLiteCatalog(db).open() as catalog:
        checkpoint = catalog.get_scale_s0_locator_preprovider_checkpoint(
            execution_attempt_id=attempt.attempt_id, authority_hash=authority.hash)
        assert checkpoint is not None
        assert checkpoint["material"]["authority"] == authority.material()
        assert checkpoint["material"]["frozen_subjects"] == [item.material() for item in frozen]
        assert checkpoint["material"]["a3_state"] == "pending"
        for table in ("scale_s0_attestation_windows", "budget_reservations", "provider_request_attempts"):
            with catalog._connection() as conn:
                assert conn.execute(f"SELECT count(*) FROM {table}").fetchone()[0] == 0

    # Re-enter through the production CLI with hostile A3 variants.  These
    # must fail before any durable reservation or provider construction.
    bad_hash = list(argv)
    bad_hash[bad_hash.index("--execution-authority") + 1] = "f" * 64
    with pytest.raises(ScalePreflightError, match="hash does not match"):
        main(bad_hash)
    stale = list(argv)
    stale[stale.index("--observed-at") + 1] = (datetime.now(timezone.utc) - timedelta(days=2)).isoformat()
    with pytest.raises(ScalePreflightError, match="stale"):
        main(stale)
    authority_path.write_text('{"schema":"malformed"}', encoding="utf-8")
    with pytest.raises(ScalePreflightError, match="legacy or incomplete"):
        main(argv)
    with SQLiteCatalog(db).open() as catalog:
        for table in ("scale_s0_attestation_windows", "budget_reservations", "provider_request_attempts"):
            with catalog._connection() as conn:
                assert conn.execute(f"SELECT count(*) FROM {table}").fetchone()[0] == 0


def test_structured_a3_preflight_rejects_incomplete_inputs_before_provider(tmp_path):
    # Argument completeness is covered at the production boundary, not just
    # by authority helper tests.
    db = tmp_path / "empty.sqlite3"
    SQLiteCatalog(db).open(initialize=True).close()
    work = tmp_path / "work.json"; work.write_text("{}", encoding="utf-8")
    with pytest.raises(SystemExit, match="structured preflight requires complete explicit A3 fields"):
        main(["--catalog", str(db), "--attempt-id", "attempt:s0:21", "--builder-commit-sha", "a" * 40,
              "--runtime-root", str(tmp_path), "--work", str(work), "--preflight", "--cohort-id", "x"])
    # An entirely omitted A3 tuple was previously able to bypass the
    # conditional validation branch when the work list was empty.
    with pytest.raises(SystemExit, match="structured preflight requires complete explicit A3 fields"):
        main(["--catalog", str(db), "--attempt-id", "attempt:s0:21", "--builder-commit-sha", "a" * 40,
              "--runtime-root", str(tmp_path), "--work", str(work), "--preflight"])
