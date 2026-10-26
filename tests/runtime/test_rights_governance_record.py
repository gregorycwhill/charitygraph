"""Provider-free tests for the private rights-record authority substrate."""

from __future__ import annotations

import hashlib
import json
import os
from datetime import date, datetime, timezone
from pathlib import Path

import pytest
from pydantic import ValidationError

from charitygraph.runtime.rights_governance_record import (
    FORMAT_VERSION,
    SCHEMA_ID,
    SCHEMA_VERSION,
    RightsAxis,
    RightsGovernanceError,
    RightsGovernanceEvent,
    RightsGovernanceRecord,
    RightsGovernanceStore,
    RightsStorageError,
    export_record,
    import_record,
    resolve_current,
    validate_history,
)
from charitygraph.contracts import AcquisitionReceipt, ProducerRef, PropositionAuthorityRole, SourceDefinition, SourceRecord, deterministic_id
from charitygraph.runtime import SQLiteCatalog
from charitygraph.source_rights import ArtifactRightsDecision


RECORDED_AT = datetime(2026, 10, 26, 0, 0, tzinfo=timezone.utc)


def _record(**changes: object) -> RightsGovernanceRecord:
    values: dict[str, object] = {
        "decision_id": "rights:fixture:decision-1",
        "source_artifact_id": "srcblob:fixture-source",
        "source_record_id": "srcrec:fixture-record",
        "source_origin_url": "https://example.invalid/fixture",
        "source_role": "source-native",
        "acquisition_lineage_ids": ("acq:receipt-b", "acq:receipt-a"),
        "representation_artifact_id": "artifact:fixture-representation",
        "representation_sha256": "1" * 64,
        "rights_basis": "public_facts_only",
        "rights_policy_id": "PUBLIC_FACTS_ONLY_V1",
        "rights_policy_version": "1.0.0",
        "provider_processing_policy_id": "OPENAI_API_BUSINESS_NO_TRAINING_DEFAULT_AS_OF_2026_09_13_V1",
        "provider_processing_policy_version": "1.0.0",
        "purpose": "bounded provider-free fixture validation",
        "scope": "scope:fixture-a",
        "evidence_locator": "source-record:fixture-record#field",
        "evidence_sha256": "2" * 64,
        "assessed_on": date(2026, 10, 26),
        "local_retention": RightsAxis(
            status="authorized",
            policy_id="CG_BOUNDED_LOCAL_ANALYTICAL_RETENTION_V1",
            policy_version="1.0.0",
            decision_id="rights:fixture:retention-1",
        ),
        "provider_transmission": RightsAxis(
            status="authorized",
            policy_id="OPENAI_API_BUSINESS_NO_TRAINING_DEFAULT_AS_OF_2026_09_13_V1",
            policy_version="1.0.0",
            decision_id="rights:fixture:provider-1",
        ),
        "public_redistribution": RightsAxis(status="blocked"),
        "status": "authorized",
        "review_status": "current",
        "actor_kind": "human",
        "actor_id": "actor:fixture-reviewer",
        "actor_version": "review-policy:fixture-1",
        "recorded_at": RECORDED_AT,
    }
    values.update(changes)
    values.pop("record_id", None)
    return RightsGovernanceRecord.model_validate(values)


def test_canonical_identity_is_utf8_hashed_and_reordered_equivalents_match():
    left = _record(acquisition_lineage_ids=("acq:receipt-a", "acq:receipt-b"))
    right = _record(acquisition_lineage_ids=("acq:receipt-b", "acq:receipt-a"))

    assert left.content_hash == right.content_hash
    assert export_record(left).decode("utf-8").encode("utf-8") == export_record(left)
    assert hashlib.sha256(export_record(left)).hexdigest() == left.content_hash
    assert json.loads(export_record(left)) == {
        "format_version": FORMAT_VERSION,
        "schema_id": SCHEMA_ID,
        "schema_version": SCHEMA_VERSION,
        "record": json.loads(export_record(right))["record"],
    }


def test_roundtrip_and_strict_import_reject_noncanonical_or_unsupported_bytes():
    record = _record()
    assert import_record(export_record(record)) == record

    reordered = json.dumps(json.loads(export_record(record)), ensure_ascii=False, indent=2).encode()
    with pytest.raises(RightsGovernanceError, match="canonical"):
        import_record(reordered)

    unsupported = json.loads(export_record(record))
    unsupported["schema_version"] = "99.0"
    with pytest.raises(RightsGovernanceError, match="unsupported"):
        import_record(json.dumps(unsupported, separators=(",", ":")).encode())

    with pytest.raises(RightsGovernanceError):
        import_record(b"not utf-8: \xff")


def test_private_store_restarts_loads_and_restores_without_sqlite_or_source_payload(tmp_path: Path):
    root = tmp_path / "private-rights"
    record = _record()
    store = RightsGovernanceStore(root)
    stored = store.put_record(record)
    assert stored == root / "records" / "sha256" / record.content_hash[:2] / f"{record.content_hash}.json"

    reopened = RightsGovernanceStore(str(root))
    assert reopened.load_record(record.content_hash) == record
    assert reopened.restore_records() == (record,)
    payload = json.loads(stored.read_bytes())["record"]
    assert all(key not in payload for key in ("prompt", "provider_receipt", "cost", "source_body"))


def test_exact_binding_and_three_rights_axes_are_explicit_and_scope_isolated():
    record = _record()
    assert record.binding_key == (
        "srcblob:fixture-source", "srcrec:fixture-record", "source-native", "1" * 64
    )
    assert record.local_retention.status == "authorized"
    assert record.provider_transmission.status == "authorized"
    assert record.public_redistribution.status == "blocked"
    other_scope = _record(scope="scope:fixture-b")
    assert len(resolve_current((record, other_scope), as_of=date(2026, 10, 26))) == 2

    with pytest.raises(ValidationError):
        _record(prompt="must-not-be-a-record-field")


def test_compatibility_matches_existing_artifact_rights_decision_and_sqlite_projection(tmp_path: Path):
    source_hash = "3" * 64
    source_url = "https://example.invalid/fixture"
    source_record_id = deterministic_id(
        "srcrec:",
        {
            "source_family": "official_website",
            "source_version": None,
            "source_locator": source_url,
            "payload_hash": source_hash,
        },
    )
    record = _record(
        source_record_id=source_record_id,
        acquisition_lineage_ids=("acq:rights-record-test",),
    )
    legacy = ArtifactRightsDecision(
        decision_id=record.decision_id,
        source_artifact_id=record.source_artifact_id,
        representation_artifact_id=record.representation_artifact_id,
        source_record_id=record.source_record_id,
        source_origin_url=record.source_origin_url,
        source_role=record.source_role,
        acquisition_lineage_ids=record.acquisition_lineage_ids,
        transmitted_representation_sha256=record.representation_sha256,
        rights_policy_id=record.rights_policy_id,
        rights_policy_version=record.rights_policy_version,
        provider_processing_policy_id=record.provider_processing_policy_id or "provider-policy",
        provider_processing_policy_version=record.provider_processing_policy_version,
        rights_basis=record.rights_basis,
        evidence_locator=record.evidence_locator,
        evidence_sha256=record.evidence_sha256,
        assessed_on=record.assessed_on,
        assessment_scope=record.scope,
        assessment_authority=record.actor_id,
        local_retention_allowed=record.local_retention.status == "authorized",
        provider_transmission_allowed=record.provider_transmission.status == "authorized",
        public_redistribution_allowed=record.public_redistribution.status == "authorized",
        factual_representation_only=True,
        representation_class="structured_factual",
    )
    assert record.decision_id == legacy.decision_id
    assert record.source_artifact_id == legacy.source_artifact_id
    assert record.source_record_id == legacy.source_record_id
    assert record.source_role == legacy.source_role
    assert record.representation_sha256 == legacy.transmitted_representation_sha256
    assert record.rights_basis == legacy.rights_basis
    assert record.rights_policy_id == legacy.rights_policy_id

    catalog = SQLiteCatalog(tmp_path / "catalog.sqlite3").open(initialize=True)
    producer = ProducerRef(kind="code", producer_id="rights-record-test", version="1")
    catalog.index_artifact(
        artifact_id=record.source_artifact_id,
        content_hash=source_hash,
        schema_id="urn:charitygraph:builder:schema:source:1.0",
        schema_version="1.0",
        storage_path="private/source",
        availability="available",
        created_at=RECORDED_AT,
        indexed_at=RECORDED_AT,
    )
    catalog.index_artifact(
        artifact_id=record.representation_artifact_id or "",
        content_hash=str(record.representation_sha256),
        schema_id="urn:charitygraph:builder:schema:representation:1.0",
        schema_version="1.0",
        storage_path="private/representation",
        availability="available",
        created_at=RECORDED_AT,
        indexed_at=RECORDED_AT,
    )
    catalog.register_source_definition(SourceDefinition(
        record_id="srcdef:rights-record-test",
        created_at=RECORDED_AT,
        producer=producer,
        publisher="fixture-publisher",
        source_class="official_website",
        authority_roles=(PropositionAuthorityRole(proposition="factual", role="source-native"),),
        acquisition_locator=source_url,
        temporal_semantics="retrieval snapshot",
        publication_eligibility="private review only",
        steward="fixture",
    ))
    catalog.record_acquisition_receipt(AcquisitionReceipt(
        record_id="acq:rights-record-test",
        created_at=RECORDED_AT,
        producer=producer,
        source_definition_id="srcdef:rights-record-test",
        requested_locator=source_url,
        resolved_locator=source_url,
        retrieved_at=RECORDED_AT,
        outcome="available",
        content_hash=source_hash,
        byte_size=1,
        artifact_id=record.source_artifact_id,
    ))
    catalog.register_source_record(SourceRecord(
        record_id=record.source_record_id,
        created_at=RECORDED_AT,
        producer=producer,
        source_family="official_website",
        source_role=record.source_role,
        source_locator=source_url,
        observed_at=RECORDED_AT,
        payload_ref=record.source_artifact_id,
        payload_hash=source_hash,
    ))
    row = catalog.record_artifact_rights_decision(legacy, now=RECORDED_AT)
    assert row["decision_id"] == record.decision_id
    assert json.loads(row["material_json"])["decision"]["source_record_id"] == record.source_record_id
    catalog.close()


def test_optional_expiry_absent_equality_accepted_and_later_blocked():
    no_expiry = _record()
    equal = _record(expires_on=date(2026, 10, 26))
    later = _record(expires_on=date(2026, 10, 25))
    assert no_expiry.can_promote(as_of=date(2026, 10, 26))
    assert equal.can_promote(as_of=date(2026, 10, 26))
    assert not later.can_promote(as_of=date(2026, 10, 26))
    assert resolve_current((equal,), as_of=date(2026, 10, 26)) == (equal,)
    assert resolve_current((later,), as_of=date(2026, 10, 26)) == ()


def test_supersession_and_revocation_are_append_only_and_history_is_non_mutating():
    original = _record()
    original_bytes = export_record(original)
    replacement = _record(
        decision_id="rights:fixture:decision-2",
        recorded_at=datetime(2026, 10, 27, tzinfo=timezone.utc),
        supersedes_record_id=original.content_hash,
    )
    assert resolve_current((original, replacement), as_of=date(2026, 10, 27)) == (replacement,)
    assert export_record(original) == original_bytes

    revoked = _record(
        decision_id="rights:fixture:revocation-1",
        status="revoked",
        review_status="revoked",
        provider_transmission=RightsAxis(status="revoked"),
        revokes_record_id=original.content_hash,
        recorded_at=datetime(2026, 10, 28, tzinfo=timezone.utc),
    )
    assert resolve_current((original, revoked), as_of=date(2026, 10, 28)) == ()
    assert export_record(original) == original_bytes
    with pytest.raises(RightsGovernanceError, match="crosses"):
        validate_history((original, _record(scope="scope:fixture-b", revokes_record_id=original.content_hash)))

    event = RightsGovernanceEvent(
        record_id=original.content_hash,
        event_type="reviewed",
        actor_kind="human",
        actor_id="actor:fixture-reviewer",
        recorded_at=RECORDED_AT,
        note="offline review event",
    )
    # The event model is tested without invoking its store; the actual file-backed
    # append-only check is covered below in a fresh private root.
    assert event.event_id == hashlib.sha256(event.canonical_bytes()).hexdigest()


def test_store_event_append_does_not_mutate_record_and_duplicate_write_is_idempotent(tmp_path: Path):
    record = _record()
    store = RightsGovernanceStore(tmp_path / "root")
    path = store.put_record(record)
    original = path.read_bytes()
    assert store.put_record(record) == path
    assert path.read_bytes() == original
    event = RightsGovernanceEvent(
        record_id=record.content_hash,
        event_type="created",
        actor_kind="code",
        actor_id="code:rights-governance-record",
        recorded_at=RECORDED_AT,
    )
    event_path = store.put_event(event)
    assert store.load_event(event.event_id) == event
    assert path.read_bytes() == original
    assert event_path != path


def test_corruption_collision_and_invalid_hash_fail_closed(tmp_path: Path):
    record = _record()
    store = RightsGovernanceStore(tmp_path / "root")
    path = store.put_record(record)
    path.write_bytes(path.read_bytes()[:-1] + b"0")
    with pytest.raises(RightsStorageError, match="hash"):
        store.load_record(record.content_hash)
    with pytest.raises(RightsStorageError, match="collision"):
        store.put_record(record)

    with pytest.raises(ValidationError):
        _record(representation_sha256="not-a-sha256")
    with pytest.raises(ValidationError):
        _record(evidence_sha256="A" * 64)


def test_unsupported_basis_unknown_role_and_ambiguous_input_fail_closed():
    with pytest.raises(ValidationError):
        _record(rights_basis="invented_basis")
    with pytest.raises(ValidationError, match="unknown or version-mismatched"):
        _record(rights_policy_id="RIGHTS_POLICY_DOES_NOT_EXIST")
    with pytest.raises(ValidationError, match="unknown or ambiguous"):
        _record(source_role="ambiguous")
    with pytest.raises(ValidationError, match="unknown or ambiguous"):
        _record(scope="unknown")
    with pytest.raises(ValidationError, match="authorized rights axis"):
        RightsAxis(status="authorized")
    with pytest.raises(ValidationError, match="not_assessed"):
        RightsAxis(status="not_assessed", decision_id="rights:unassessed")


def test_impossible_chains_and_ambiguous_current_records_fail_closed():
    first = _record()
    second = _record(
        decision_id="rights:fixture:decision-2",
        recorded_at=datetime(2026, 10, 27, tzinfo=timezone.utc),
        supersedes_record_id=first.content_hash,
    )
    third = _record(
        decision_id="rights:fixture:decision-3",
        recorded_at=datetime(2026, 10, 28, tzinfo=timezone.utc),
        supersedes_record_id=first.content_hash,
    )
    with pytest.raises(RightsGovernanceError, match="ambiguous successors"):
        validate_history((first, second, third))
    with pytest.raises(RightsGovernanceError, match="missing"):
        validate_history((_record(supersedes_record_id="f" * 64),))
    with pytest.raises(ValidationError, match="both supersede"):
        _record(
            supersedes_record_id=first.content_hash,
            revokes_record_id=first.content_hash,
            decision_id="rights:fixture:impossible",
            provider_transmission=RightsAxis(status="blocked"),
        )

    left = _record(decision_id="rights:fixture:parallel-a")
    right = _record(decision_id="rights:fixture:parallel-b", actor_id="actor:other")
    with pytest.raises(RightsGovernanceError, match="ambiguous"):
        resolve_current((left, right), as_of=date(2026, 10, 26))


def test_path_traversal_unsafe_root_and_link_redirection_are_rejected(tmp_path: Path):
    with pytest.raises(RightsStorageError, match="absolute"):
        RightsGovernanceStore("relative-rights-root")
    with pytest.raises(RightsStorageError, match="dedicated"):
        RightsGovernanceStore(Path(tmp_path.anchor))

    symlink_root = tmp_path / "symlink-root"
    target = tmp_path / "real-root"
    try:
        os.symlink(target, symlink_root, target_is_directory=True)
    except (OSError, NotImplementedError):
        symlink_root = None
    if symlink_root is not None:
        with pytest.raises(RightsStorageError, match="symlink"):
            RightsGovernanceStore(symlink_root)

    store = RightsGovernanceStore(tmp_path / "hardlink-root")
    record = _record()
    path = store.put_record(record)
    hardlink = path.with_name("not-the-address.json")
    try:
        os.link(path, hardlink)
    except (OSError, NotImplementedError):
        return
    with pytest.raises(RightsStorageError, match="unsafe link"):
        store.load_record(record.content_hash)


def test_no_provider_task_attempt_reservation_cost_or_external_side_effects():
    record = _record()
    assert not any(
        field in record.model_dump()
        for field in ("task_id", "attempt_id", "reservation_id", "cost", "provider_receipt")
    )
    assert resolve_current((record,), as_of=date(2026, 10, 26)) == (record,)
