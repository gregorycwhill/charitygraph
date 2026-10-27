"""Provider-free tests for the versioned private rights projection."""

from __future__ import annotations

import hashlib
import sqlite3
from datetime import date, datetime, timezone
from pathlib import Path

import pytest
from pydantic import ValidationError

import charitygraph.runtime.catalog as catalog_module
from charitygraph.runtime.migrations import MIGRATIONS, SUPPORTED_VERSION
from charitygraph.runtime.rights_governance_projection import (
    RightsGovernanceProjection,
    RightsProjectionError,
)
from charitygraph.runtime.rights_governance_record import (
    RightsAxis,
    RightsGovernanceError,
    RightsGovernanceEvent,
    RightsGovernanceRecord,
    RightsGovernanceStore,
    resolve_current,
    validate_history,
)


AS_OF = date(2026, 10, 27)
RECORDED_AT = datetime(2026, 10, 27, tzinfo=timezone.utc)


def _record(**changes: object) -> RightsGovernanceRecord:
    values: dict[str, object] = {
        "decision_id": "rights:projection:decision-1",
        "source_artifact_id": "srcblob:projection-source",
        "source_record_id": "srcrec:projection-record",
        "subject_id": "subject:projection",
        "source_origin_url": "https://example.invalid/projection",
        "source_role": "source-native",
        "acquisition_lineage_ids": ("acq:projection-a",),
        "representation_artifact_id": "artifact:projection-representation",
        "representation_sha256": "1" * 64,
        "rights_basis": "explicit_open_license",
        "rights_policy_id": "CC_BY_4_0_V1",
        "rights_policy_version": "1.0.0",
        "provider_processing_policy_id": "OPENAI_API_BUSINESS_NO_TRAINING_DEFAULT_AS_OF_2026_09_13_V1",
        "provider_processing_policy_version": "1.0.0",
        "purpose": "semantic_analysis",
        "scope": "scope:projection",
        "evidence_locator": "source-record:projection#field",
        "evidence_sha256": "2" * 64,
        "assessed_on": AS_OF,
        "attribution": "Fixture publisher",
        "licence_identifier": "CC BY 4.0",
        "licence_or_terms_url": "https://creativecommons.org/licenses/by/4.0/",
        "representation_class": "structured_factual",
        "factual_representation_only": True,
        "lawful_access_confirmed": True,
        "circumvention_used": False,
        "explicit_prohibition_found": False,
        "one_source_native_entity_record": True,
        "retention_lifecycle_status": "active_until_review",
        "retention_review_due_on": date(2027, 9, 14),
        "local_retention": RightsAxis(
            status="authorized",
            policy_id="CG_BOUNDED_LOCAL_ANALYTICAL_RETENTION_V1",
            policy_version="1.0.0",
            decision_id="rights:projection:retention-1",
        ),
        "provider_transmission": RightsAxis(status="blocked"),
        "public_redistribution": RightsAxis(status="blocked"),
        "status": "authorized",
        "review_status": "current",
        "actor_kind": "human",
        "actor_id": "actor:projection-reviewer",
        "actor_version": "review-policy:projection-1",
        "recorded_at": RECORDED_AT,
    }
    values.update(changes)
    values.pop("record_id", None)
    return RightsGovernanceRecord.model_validate(values)


def _event(record: RightsGovernanceRecord, *, event_type: str = "created") -> RightsGovernanceEvent:
    return RightsGovernanceEvent(
        record_id=record.content_hash,
        event_type=event_type,
        actor_kind="human",
        actor_id="actor:projection-reviewer",
        recorded_at=RECORDED_AT,
        note="provider-free fixture",
    )


def _open_projection(path: Path) -> RightsGovernanceProjection:
    projection = RightsGovernanceProjection(path).open(initialize=True)
    assert projection.migrate() == SUPPORTED_VERSION
    return projection


def test_v28_catalog_migrates_to_numbered_v29_projection_and_checksum_is_present(tmp_path: Path, monkeypatch):
    path = tmp_path / "v28.sqlite3"
    original = catalog_module.MIGRATIONS
    monkeypatch.setattr(catalog_module, "MIGRATIONS", tuple(item for item in MIGRATIONS if item.version <= 28))
    prior = RightsGovernanceProjection(path).open(initialize=True)
    assert prior.migrate() == 28
    prior.close()
    monkeypatch.setattr(catalog_module, "MIGRATIONS", original)

    upgraded = RightsGovernanceProjection(path).open()
    assert upgraded.migrate() == 29
    with sqlite3.connect(path) as conn:
        migration = conn.execute("SELECT version, name, checksum FROM schema_migrations WHERE version=29").fetchone()
        assert migration == (29, MIGRATIONS[-1].name, MIGRATIONS[-1].checksum)
        assert conn.execute("SELECT name FROM sqlite_master WHERE name='rights_projection_current'").fetchone()
    upgraded.close()


def test_rebuild_restart_and_idempotence_hold_only_safe_metadata(tmp_path: Path):
    private_root = tmp_path / "private-rights"
    store = RightsGovernanceStore(private_root)
    record = _record()
    store.put_record(record)
    store.put_event(_event(record))

    projection = _open_projection(tmp_path / "projection.sqlite3")
    first_hash = projection.rebuild_from_store(store, as_of=AS_OF)
    first = projection.snapshot()
    assert first["records"][0]["record_id"] == record.content_hash
    assert first["records"][0]["provider_transmission_status"] == "blocked"
    assert first["current"][0]["record_id"] == record.content_hash
    assert first["events"][0]["record_id"] == record.content_hash
    assert "source_body" not in first["records"][0]
    assert "material_json" not in first["records"][0]
    projection.close()

    reopened = _open_projection(tmp_path / "projection.sqlite3")
    assert reopened.snapshot_hash() == first_hash
    assert reopened.rebuild_from_store(store, as_of=AS_OF) == first_hash
    assert reopened.snapshot() == first
    reopened.close()


def test_corrupt_record_hash_and_missing_event_target_fail_closed(tmp_path: Path):
    private_root = tmp_path / "private-rights"
    store = RightsGovernanceStore(private_root)
    record = _record()
    path = store.put_record(record)
    path.write_bytes(path.read_bytes() + b"corruption")
    projection = _open_projection(tmp_path / "projection.sqlite3")
    with pytest.raises(RightsProjectionError, match="projection input"):
        projection.rebuild_from_store(store, as_of=AS_OF)
    projection.close()

    missing_store = RightsGovernanceStore(tmp_path / "missing-event-rights")
    missing = _record(scope="scope:missing-event")
    missing_store.put_record(missing)
    event = _event(missing)
    event_path = missing_store.root / "events" / "sha256" / event.event_id[:2] / f"{event.event_id}.json"
    event_path.parent.mkdir(parents=True)
    event_path.write_bytes(event.canonical_bytes())
    # Move the event's target out of the authoritative store after creating a
    # valid event object; projection ingestion must still reject the missing link.
    target = missing_store.root / "records" / "sha256" / missing.content_hash[:2] / f"{missing.content_hash}.json"
    target.unlink()
    with pytest.raises(RightsProjectionError):
        projection = _open_projection(tmp_path / "missing-event.sqlite3")
        projection.rebuild_from_store(missing_store, as_of=AS_OF)


def test_transactional_rollback_preserves_previous_projection_on_failure(tmp_path: Path, monkeypatch):
    store = RightsGovernanceStore(tmp_path / "private-rights")
    first = _record()
    store.put_record(first)
    projection = _open_projection(tmp_path / "projection.sqlite3")
    projection.rebuild_from_store(store, as_of=AS_OF)
    before = projection.snapshot()

    original = projection._insert_record
    calls = 0

    def fail_after_one(conn, record):
        nonlocal calls
        calls += 1
        original(conn, record)
        if calls == 1:
            raise RightsProjectionError("injected rebuild failure")

    second = _record(scope="scope:second")
    store.put_record(second)
    monkeypatch.setattr(projection, "_insert_record", fail_after_one)
    with pytest.raises(RightsProjectionError, match="injected"):
        projection.rebuild_from_store(store, as_of=AS_OF)
    assert projection.snapshot() == before
    projection.close()


def test_lifecycle_conflicts_and_policy_states_never_over_authorize(tmp_path: Path):
    base = _record()
    cross_binding = _record(scope="scope:other", supersedes_record_id=base.content_hash)
    with pytest.raises(RightsGovernanceError, match="crosses representation or scope"):
        validate_history((base, cross_binding))

    left = _record(actor_id="actor:left")
    right = _record(actor_id="actor:right")
    with pytest.raises(RightsGovernanceError, match="multiple eligible"):
        resolve_current((left, right), as_of=AS_OF)

    cycle_left = base.model_copy(update={"record_id": "a" * 64, "supersedes_record_id": "b" * 64})
    cycle_right = base.model_copy(update={"record_id": "b" * 64, "supersedes_record_id": "a" * 64})
    with pytest.raises(RightsGovernanceError, match="cycle"):
        validate_history((cycle_left, cycle_right))

    with pytest.raises(ValidationError, match="unknown or version-mismatched"):
        _record(rights_policy_version="9.9.9")
    with pytest.raises(ValidationError, match="no exact provider policy version mapping"):
        _record(
            provider_transmission=RightsAxis(
                status="authorized",
                policy_id="OPENAI_API_BUSINESS_NO_TRAINING_DEFAULT_AS_OF_2026_09_13_V1",
                policy_version="1.0.0",
                decision_id="rights:projection:provider-authorized",
            ),
        )

    expired = _record(scope="scope:expired", expires_on=date(2026, 10, 26))
    due = _record(scope="scope:due", review_status="review_due")
    revoked = _record(
        scope="scope:revoked",
        status="revoked",
        review_status="revoked",
        local_retention=RightsAxis(status="revoked"),
    )
    assert resolve_current((expired, due, revoked), as_of=AS_OF) == ()


def test_projection_schema_enforces_unique_current_rows(tmp_path: Path):
    store = RightsGovernanceStore(tmp_path / "private-rights")
    record = _record()
    store.put_record(record)
    projection = _open_projection(tmp_path / "projection.sqlite3")
    projection.rebuild_from_store(store, as_of=AS_OF)
    with projection._catalog._connection(immediate=True) as conn:
        with pytest.raises(sqlite3.IntegrityError):
            conn.execute(
                "INSERT INTO rights_projection_current(binding_hash, record_id, as_of) VALUES (?,?,?)",
                (next(iter(projection.snapshot()["current"]))["binding_hash"], record.content_hash, AS_OF.isoformat()),
            )
    projection.close()
