from datetime import datetime, timezone

import pytest

from charitygraph.runtime import ConflictError, SQLiteCatalog


def record(**changes):
    value = {
        "attempt_id": "attempt:s0:18", "run_id": "run:s0:attempt-18",
        "terminal_state": "consumed_non_resumable",
        "terminal_reason": "zero_crossing_obsolete_non_resumable",
        "provider_crossings": "zero", "reservation_state": "not_created",
        "a3_state": "not_created", "checkpoint_state": "preprovider_only",
        "evidence": {"authority_id": "CG-S0-PO-ATTEMPT18-2026-09-26", "checkpoint_sha256": "a" * 64},
        "recorded_at": datetime(2026, 9, 26, tzinfo=timezone.utc).isoformat(),
    }
    value.update(changes)
    return value


def test_terminal_replay_and_conflict_are_fail_closed(tmp_path):
    catalog = SQLiteCatalog(tmp_path / "state.sqlite3").open(initialize=True)
    first = catalog.register_scale_s0_historical_terminal(record())
    assert catalog.register_scale_s0_historical_terminal(record())["material_hash"] == first["material_hash"]
    with pytest.raises(ConflictError):
        catalog.register_scale_s0_historical_terminal(record(terminal_reason="tampered"))
    with pytest.raises(ConflictError):
        catalog.register_run({"record_id": "run:s0:attempt-18", "run_kind": "s0", "status": "planned", "configuration_hash": "x", "created_at": record()["recorded_at"]})


def test_terminal_live_collision_is_rejected(tmp_path):
    catalog = SQLiteCatalog(tmp_path / "state.sqlite3").open(initialize=True)
    catalog.register_scale_s0_historical_terminal(record())
    with pytest.raises(ConflictError):
        catalog.register_scale_s0_execution_attempt({"attempt_id": "attempt:s0:18", "mandate_id": "m", "mandate_hash": "h", "slice_id": "s", "run_id": "run:s0:attempt-18", "builder_repository": "b", "builder_commit_sha": "0" * 40, "data_repository": "d", "data_commit_sha": "1" * 40, "bridge_certification": "x", "bridge_version": "1", "schema_version": 28, "recovery_authority_ref": "r", "configuration_hash": "x", "status": "prepared", "created_at": record()["recorded_at"]})


def test_unknown_operational_fields_are_explicit(tmp_path):
    catalog = SQLiteCatalog(tmp_path / "state.sqlite3").open(initialize=True)
    row = catalog.register_scale_s0_historical_terminal(record(provider_crossings="unknown", reservation_state="unknown", a3_state="unknown", checkpoint_state="unknown"))
    assert row["provider_crossings"] == "unknown"
    assert row["reservation_state"] == "unknown"
