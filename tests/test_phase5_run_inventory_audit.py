from __future__ import annotations

from copy import deepcopy

import pytest

from charitygraph.phase5_run_inventory_audit import (
    SCHEMA,
    RunInventoryAuditError,
    audit_phase5_run_inventory,
    run_inventory_audit_sha256,
)


AS_OF = "2026-11-01T12:00:00+00:00"
SHA_A = "a" * 64
SHA_B = "b" * 64


def source(source_id: str, role: str, run_ids: list[str], **extra):
    value = {
        "source_id": source_id,
        "source_identity": source_id,
        "source_role": role,
        "source_byte_sha256": SHA_A if source_id.endswith("a") else SHA_B,
        "observed_at": "2026-11-01T10:00:00+00:00",
        "scope": {"scope_id": "phase5", "kind": "bounded"},
        "schema_version": 1,
        "run_ids": run_ids,
        "missingness": {"state": "observed", "missing_ids": []},
        "provenance": {"capture": "fixture", "basis": "existing-record"},
    }
    value.update(extra)
    return value


def audit(*sources_):
    return audit_phase5_run_inventory(list(sources_), as_of=AS_OF).document


def test_schema_and_observed_subset_are_typed_and_non_authoritative():
    document = audit(source("index-a", "run_index", ["run:b", "run:a"]))
    assert document["schema"] == SCHEMA
    assert document["status"] == "NOT_AUTHORITATIVE"
    assert document["authority"] == {
        "status": "UNVERIFIED",
        "project_wide_authoritative": False,
        "authoritative_total": None,
        "remaining_spend": None,
        "basis": "no authenticated source-owned project-wide completeness adapter is present",
    }
    assert document["coverage"]["known_observed_subset"] == ["run:a", "run:b"]


def test_self_declared_complete_source_never_grants_authority():
    document = audit(source("index-a", "run_index", ["run:a"], source_owned=True, authenticated=True, complete=True))
    assert document["authority"]["project_wide_authoritative"] is False
    assert "SELF_DECLARED_SOURCE_OWNERSHIP_UNVERIFIED" in document["reason_codes"]
    assert "CALLER_ASSERTED_PROVENANCE_UNVERIFIED" in document["reason_codes"]


def test_forged_complete_manifest_fields_are_only_diagnostic():
    document = audit(source(
        "forged", "run_index", ["run:a"], source_owned=True, authenticated=True, complete=True,
        provenance={"attestation": "forged-complete-project-manifest"}, scope={"scope_id": "project", "kind": "project_wide"},
    ))
    assert document["authority"]["authoritative_total"] is None
    assert document["authority"]["remaining_spend"] is None
    assert "PROJECT_WIDE_COMPLETENESS_UNVERIFIED" in document["reason_codes"]


def test_duplicate_ids_are_reported_and_unique_subset_is_preserved():
    document = audit(source("index-a", "run_index", ["run:a", "run:a", "run:b"]))
    assert document["coverage"]["known_observed_subset"] == ["run:a", "run:b"]
    assert list(document["coverage"]["duplicate_run_ids_by_source"].values()) == [["run:a"]]
    assert "DUPLICATE_RUN_IDS" in document["reason_codes"]


def test_omitted_and_orphaned_ids_are_exact_and_sorted():
    document = audit(
        source("index-a", "run_index", ["run:a", "run:b"]),
        source("export-b", "runtime_export", ["run:b", "run:c"]),
    )
    omitted = next(iter(document["coverage"]["omitted_run_ids_by_source"].values()))
    assert omitted in (["run:c"], ["run:a"])
    assert document["coverage"]["orphaned_run_ids_by_source"]["export-b|runtime_export|" + SHA_B] == ["run:c"]
    assert "OMITTED_RUN_IDS" in document["reason_codes"]
    assert "ORPHANED_RUN_IDS" in document["reason_codes"]


def test_conflicting_run_metadata_is_surface_without_guessing():
    document = audit(
        source("index-a", "run_index", ["run:a"], scope={"scope_id": "one", "kind": "bounded"}),
        source("export-b", "runtime_export", ["run:a"], scope={"scope_id": "two", "kind": "bounded"}),
    )
    assert document["coverage"]["conflicting_run_ids"] == ["run:a"]
    assert "CONFLICTING_RUN_METADATA" in document["reason_codes"]


def test_run_source_identity_mismatch_is_reported():
    document = audit(
        source("index-a", "run_index", ["run:a"], run_records=[{"run_id": "run:a", "source_identity": "alpha"}]),
        source("export-b", "runtime_export", ["run:a"], run_records=[{"run_id": "run:a", "source_identity": "beta"}]),
    )
    assert document["coverage"]["source_identity_mismatch_run_ids"] == ["run:a"]
    assert "SOURCE_IDENTITY_MISMATCH" in document["reason_codes"]


def test_same_local_source_views_do_not_count_as_independent():
    document = audit(
        source("same-db", "run_index", ["run:a"], source_identity="same-db"),
        source("same-db", "runtime_export", ["run:a"], source_identity="same-db"),
    )
    assert document["coverage"]["independent_source_count"] == 1
    assert "SAME_SOURCE_FALSE_INDEPENDENCE" in document["reason_codes"]


def test_missing_sha_is_fail_closed_but_record_is_retained():
    value = source("index-a", "run_index", ["run:a"])
    del value["source_byte_sha256"]
    document = audit(value)
    assert document["sources"][0]["run_ids"] == ["run:a"]
    assert document["sources"][0]["evidence_digest"] is None
    assert "MISSING_SOURCE_DIGEST" in document["reason_codes"]


def test_malformed_and_stale_schema_are_visible():
    document = audit(source("index-a", "run_index", ["run:a"], schema_version=99))
    assert "STALE_OR_UNSUPPORTED_SOURCE_SCHEMA_VERSION" in document["reason_codes"]
    malformed = audit(source("index-a", "run_index", ["run:a"], schema_version="v1"))
    assert "MALFORMED_SOURCE_SCHEMA_VERSION" in malformed["reason_codes"]


def test_stale_evidence_and_source_silence_are_visible():
    document = audit(source(
        "index-a", "run_index", [], observed_at="2020-01-01T00:00:00+00:00",
        stale_after="2026-01-01T00:00:00+00:00", missingness={"state": "silent", "missing_ids": []},
    ))
    assert "STALE_SOURCE_EVIDENCE" in document["reason_codes"]
    assert "SOURCE_SILENCE_OR_EMPTY" in document["reason_codes"]


def test_unknown_provider_receipt_run_is_not_promoted():
    document = audit(
        source("index-a", "run_index", ["run:a"]),
        source("receipts-b", "provider_receipt_population", ["run:a", "run:unknown"], provider_receipt_run_ids=["run:unknown"]),
    )
    assert document["coverage"]["orphaned_run_ids_by_source"]["receipts-b|provider_receipt_population|" + SHA_B] == ["run:unknown"]
    assert "UNKNOWN_PROVIDER_RECEIPT_RUN_IDS" in document["reason_codes"]
    assert document["authority"]["authoritative_total"] is None


def test_bridge_ledger_and_local_runs_are_not_history_authority():
    document = audit(
        source("bridge", "bridge_instruction_ledger", ["instruction:1"]),
        source("local", "local_sqlite_runs", ["run:a"]),
    )
    assert "NON_SOURCE_HISTORY_BOUNDARY" in document["reason_codes"]
    assert document["authority"]["project_wide_authoritative"] is False


def test_canonical_output_is_deterministic_under_input_order():
    left = audit_phase5_run_inventory([
        source("export-b", "runtime_export", ["run:b"]),
        source("index-a", "run_index", ["run:a"]),
    ], as_of=AS_OF)
    right = audit_phase5_run_inventory([
        source("index-a", "run_index", ["run:a"]),
        source("export-b", "runtime_export", ["run:b"]),
    ], as_of=AS_OF)
    assert left.canonical_json == right.canonical_json
    assert left.sha256 == right.sha256 == run_inventory_audit_sha256(left)


def test_same_source_key_collision_reversal_is_byte_stable():
    one = source("same", "runtime_export", ["run:b"])
    two = source("same", "runtime_export", ["run:a"])
    left = audit_phase5_run_inventory([one, two], as_of=AS_OF)
    right = audit_phase5_run_inventory([two, one], as_of=AS_OF)

    assert left.canonical_json == right.canonical_json
    assert left.sha256 == right.sha256 == run_inventory_audit_sha256(left)
    assert [item["run_ids"] for item in left.document["sources"]] == [["run:a"], ["run:b"]]
    assert [item["source_key"].rsplit("#", 1)[-1] for item in left.document["sources"]] == ["1", "2"]
    assert "SAME_SOURCE_FALSE_INDEPENDENCE" in left.document["reason_codes"]


def test_three_same_source_key_collisions_have_stable_suffixes():
    sources = [
        source("same", "runtime_export", ["run:c"]),
        source("same", "runtime_export", ["run:a"]),
        source("same", "runtime_export", ["run:b"]),
    ]
    left = audit_phase5_run_inventory(sources, as_of=AS_OF)
    right = audit_phase5_run_inventory(list(reversed(sources)), as_of=AS_OF)

    assert left.canonical_json == right.canonical_json
    assert left.sha256 == right.sha256
    assert [item["run_ids"] for item in left.document["sources"]] == [["run:a"], ["run:b"], ["run:c"]]
    assert [item["source_key"].rsplit("#", 1)[-1] for item in left.document["sources"]] == ["1", "2", "3"]


def test_exact_duplicate_source_records_are_retained_and_byte_stable():
    one = source("same", "runtime_export", ["run:a"])
    left = audit_phase5_run_inventory([one, deepcopy(one)], as_of=AS_OF)
    right = audit_phase5_run_inventory([deepcopy(one), one], as_of=AS_OF)

    assert left.canonical_json == right.canonical_json
    assert left.sha256 == right.sha256
    assert len(left.document["sources"]) == 2
    assert [item["source_key"].rsplit("#", 1)[-1] for item in left.document["sources"]] == ["1", "2"]
    assert "SAME_SOURCE_FALSE_INDEPENDENCE" in left.document["reason_codes"]


def test_same_key_collision_preserves_source_identity_conflict_and_sha():
    one = source("same", "runtime_export", ["run:a"], source_identity="alpha")
    two = source("same", "runtime_export", ["run:a"], source_identity="beta")
    left = audit_phase5_run_inventory([one, two], as_of=AS_OF)
    right = audit_phase5_run_inventory([two, one], as_of=AS_OF)

    assert left.canonical_json == right.canonical_json
    assert left.sha256 == right.sha256 == run_inventory_audit_sha256(left)
    assert left.document["coverage"]["source_identity_mismatch_run_ids"] == ["run:a"]
    assert "SOURCE_IDENTITY_MISMATCH" in left.document["reason_codes"]


def test_invalid_top_level_request_is_rejected():
    with pytest.raises(RunInventoryAuditError):
        audit_phase5_run_inventory([], as_of=AS_OF)
    with pytest.raises(RunInventoryAuditError):
        audit_phase5_run_inventory([source("a", "run_index", ["run:a"])], as_of="not-a-time")


def test_raw_provider_payload_is_not_in_output():
    value = source(
        "index-a", "run_index", ["run:a"], raw_provider_payload="SECRET_PAYLOAD",
        provenance={"capture": "fixture", "raw_provider_payload": "SECRET_PAYLOAD"},
    )
    document = audit(value)
    assert "SECRET_PAYLOAD" not in document["sources"][0]
    assert "raw_provider_payload" not in str(document)


def test_missing_provenance_is_explicit_but_observed_ids_remain():
    value = source("index-a", "run_index", ["run:a"])
    del value["missingness"]
    del value["provenance"]
    document = audit(value)
    assert document["coverage"]["known_observed_subset"] == ["run:a"]
    assert "MISSING_MISSINGNESS_DECLARATION" in document["reason_codes"]
