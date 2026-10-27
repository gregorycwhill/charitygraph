from __future__ import annotations

import hashlib
import sqlite3
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest

from charitygraph.phase5_run_diagnostics_catalog import (
    PersistedRunDiagnosticsAdapter,
    PersistedRunDiagnosticsError,
)
from charitygraph.phase5_standard_transport import StandardCampaignCoordinator
from charitygraph.runtime import SQLiteCatalog

from test_phase5_standard_transport import FakeProvider, _row


NOW = datetime(2026, 10, 27, 1, 2, 3, tzinfo=timezone.utc)
RUN = "run:" + "a" * 32
COHORT = "cohort:" + "b" * 32
SUBJECT = "subject:" + "c" * 32
SCOPE = "scope:" + "d" * 32


def _prepare_standard_run(path: Path, *, provider: FakeProvider | None = None, run_id: str = RUN) -> tuple[SQLiteCatalog, list[dict], FakeProvider]:
    catalog = SQLiteCatalog(path).open(initialize=True)
    catalog.register_cohort(
        {
            "record_id": COHORT,
            "cohort_code": "P4C",
            "definition_version": "1",
            "membership_hash": "e" * 64,
            "budget_cap": {"amount": "10.000000", "currency": "AUD"},
            "created_at": NOW,
        }
    )
    catalog.register_run(
        {
            "record_id": run_id,
            "cohort_id": COHORT,
            "run_kind": "standard",
            "status": "planned",
            "configuration_hash": "f" * 64,
            "created_at": NOW,
        }
    )
    catalog.transition_run(run_id, "running", now=NOW)
    job_id = "deliveryjob:" + "1" * 64
    catalog.create_delivery_job(
        delivery_job_id=job_id,
        run_id=run_id,
        provider_id="openai",
        model_route="gpt-5.6-luna",
        delivery_mode="standard",
        pricing_snapshot_id="pricing:p4c",
        now=NOW,
    )
    rows = []
    for index in (1, 2):
        row = _row(index)
        task_id = row["logical_task_id"]
        request_id = row["provider_request_item_id"]
        reservation_id = "reservation:" + format(index, "064x")
        task_run_id = "taskrun:" + format(index, "064x")
        catalog.register_task(
            {
                "record_id": task_id,
                "subject_id": SUBJECT,
                "scope_id": SCOPE,
                "cohort_id": COHORT,
                "task_type": "semantic_interpretation",
                "task_schema": {"schema_id": "urn:test:p4c"},
                "cache_key": "cache:" + format(index, "064x"),
                "provider_id": "openai",
                "model_snapshot": "gpt-5.6-luna",
            },
            run_id=run_id,
            now=NOW,
        )
        catalog.reserve_cost(
            {
                "record_id": reservation_id,
                "cohort_id": COHORT,
                "run_id": run_id,
                "reserved_aud": {"amount": "1.000000", "currency": "AUD"},
                "model_task_ids": (task_id,),
            },
            now=NOW,
        )
        catalog.claim_task(task_id, owner="p4c-test", lease_expires_at=NOW + timedelta(hours=1), now=NOW)
        catalog.begin_task_attempt(
            task_id,
            owner="p4c-test",
            task_run_id=task_run_id,
            now=NOW,
            reservation_id=reservation_id,
        )
        catalog.prepare_physical_attempt(
            physical_attempt_id=row["physical_attempt_id"],
            run_id=run_id,
            subject_id=SUBJECT,
            delivery_mode="standard",
            provider_request_id=request_id,
            model_task_ids=(task_id,),
            reservation_id=reservation_id,
            now=NOW,
        )
        catalog.create_provider_request_item(
            provider_request_item_id=request_id,
            run_id=run_id,
            model_task_id=task_id,
            provider_id="openai",
            model_route="gpt-5.6-luna",
            requested_delivery_mode="standard",
            effective_service_tier="standard",
            delivery_job_id=job_id,
            physical_attempt_id=row["physical_attempt_id"],
            now=NOW,
        )
        catalog.create_provider_request_attempt(
            delivery_attempt_id=row["delivery_attempt_id"],
            provider_request_item_id=request_id,
            physical_attempt_id=row["physical_attempt_id"],
            delivery_job_id=job_id,
            attempt_ordinal=1,
            authorization_id="mandate:p4c",
            attempt_class="initial",
            predecessor_attempt_id=None,
            now=NOW,
        )
        row.update(
            {
                "run_id": run_id,
                "reservation_id": reservation_id,
                "scope_id": SCOPE,
                "evidence_ids": [],
                "contract_identity_hash": "c" * 64,
            }
        )
        rows.append(row)

    fake = provider or FakeProvider()

    def settle(row, response, usage):
        item = catalog.get_provider_request_item(row["provider_request_item_id"])
        receipt_id = item["provider_receipt_id"]
        catalog.record_accounting_actual(
            entry_key="actual:" + row["reservation_id"],
            provider_request_item_id=row["provider_request_item_id"],
            provider_receipt_id=receipt_id,
            reservation_id=row["reservation_id"],
            provider_amount="0.125000",
            provider_currency="AUD",
            accounting_amount="0.125000",
            accounting_currency="AUD",
            pricing_snapshot_id="pricing:p4c",
            fx_snapshot_id=None,
            usage=usage,
            recorded_at=NOW,
        )
        catalog.release_reservation(
            row["reservation_id"],
            {"amount": "0.875000", "currency": "AUD"},
            now=NOW,
            entry_key="release:" + row["reservation_id"],
        )

    result = StandardCampaignCoordinator(
        catalog=catalog,
        provider=fake,
        runtime_root=path.parent,
        max_concurrency=2,
        now=NOW,
        on_reconciled=settle,
    ).run(rows)
    for row in rows:
        catalog.finish_successful_attempt(
            "taskrun:" + format(int(row["logical_task_id"].split(":")[-1], 16), "064x"),
            owner="p4c-test",
            completed_at=NOW,
            result_artifact_id="artifact:p4c:" + row["logical_task_id"].split(":")[-1],
            provider_request_id=row["provider_request_item_id"],
            usage={"input_tokens": 10, "output_tokens": 2},
            pricing_snapshot_id="pricing:p4c",
        )
    if result["counts"] == {"completed": len(rows)}:
        catalog.transition_run(run_id, "succeeded", now=NOW)
    return catalog, rows, fake


def _sidecar_hashes(path: Path) -> dict[str, str]:
    values = {}
    for candidate in (path, Path(str(path) + "-wal"), Path(str(path) + "-shm")):
        if candidate.exists():
            values[str(candidate)] = hashlib.sha256(candidate.read_bytes()).hexdigest()
    return values


def test_adapter_reads_actual_persisted_standard_run_read_only_and_stable_after_restart(tmp_path: Path):
    db = tmp_path / "state.sqlite3"
    catalog, rows, provider = _prepare_standard_run(db)
    adapter = PersistedRunDiagnosticsAdapter(db, RUN)
    before_read = _sidecar_hashes(db)
    first_snapshot = adapter.read_snapshot()
    first_projection = adapter.project()
    after_read = _sidecar_hashes(db)
    assert before_read == after_read
    assert first_snapshot.schema_version == 29
    assert first_snapshot.record_counts["tasks"] == 2
    assert first_snapshot.record_counts["task_attempts"] == 2
    assert first_snapshot.record_counts["provider_receipts"] == 2
    assert first_snapshot.record_counts["reservations"] == 2
    assert first_snapshot.record_counts["cost_entries"] == 4
    assert first_projection.document["summary"]["status_counts"] == {"completed": 2}
    assert first_projection.document["summary"]["provider_posts"] == 2
    assert first_projection.document["ledger"]["actuals"] == "0.25"
    assert first_projection.document["ledger"]["releases"] == "1.75"
    assert first_projection.document["ledger"]["reconciliation"]["state"] == "RECONCILED"
    assert "snapshot:" + first_snapshot.snapshot_hash in first_projection.document["provenance"]["run_record_ref"]
    assert RUN in first_projection.document["provenance"]["run_record_ref"]

    catalog.close()
    reopened = SQLiteCatalog(db).open()
    replay = StandardCampaignCoordinator(
        catalog=reopened,
        provider=provider,
        runtime_root=tmp_path,
        max_concurrency=2,
        now=NOW,
    ).run(rows)
    assert replay["counts"] == {"replayed_terminal": 2}
    assert replay["provider_posts"] == 0
    assert len(provider.posts) == 2
    second_adapter = PersistedRunDiagnosticsAdapter(db, RUN)
    second_snapshot = second_adapter.read_snapshot()
    second_projection = second_adapter.project()
    restart_projection = second_adapter.project(restart_baseline=first_snapshot)
    assert second_snapshot.snapshot_hash == first_snapshot.snapshot_hash
    assert second_projection.sha256 == first_projection.sha256
    assert restart_projection.document["summary"]["restart_no_resend"] is True
    reopened.close()


@pytest.mark.parametrize(
    ("provider", "final_state", "classification"),
    [
        (FakeProvider(ambiguous_at=1), "held", "ambiguous"),
        (FakeProvider(systemic_at=1), "failed", "systemic"),
    ],
)
def test_adapter_preserves_distinct_ambiguous_and_systemic_stop_diagnostics(tmp_path: Path, provider, final_state, classification):
    db = tmp_path / f"{classification}.sqlite3"
    catalog, rows, _ = _prepare_standard_run(db, provider=provider, run_id=f"run:{classification}:" + "a" * 24)
    run_id = f"run:{classification}:" + "a" * 24
    catalog.transition_run(run_id, final_state, now=NOW)
    projection = PersistedRunDiagnosticsAdapter(db, run_id).project()
    stop = projection.document["summary"]["stop"]
    assert stop["campaign_stopped"] is True
    assert stop["classification"] == classification
    assert projection.document["summary"]["status_counts"] in ({"ambiguous": 1, "completed": 1}, {"failed_terminal": 1, "completed": 1})
    catalog.close()


def test_adapter_fails_closed_for_missing_run_orphan_attempt_inconsistent_receipt_unknown_state_and_cost_mismatch(tmp_path: Path):
    db = tmp_path / "invalid.sqlite3"
    catalog, rows, _ = _prepare_standard_run(db)
    catalog.close()
    adapter = PersistedRunDiagnosticsAdapter(db, RUN)
    with pytest.raises(PersistedRunDiagnosticsError, match="does not exist"):
        PersistedRunDiagnosticsAdapter(db, "run:missing").read_snapshot()

    connection = sqlite3.connect(db)
    connection.execute("UPDATE runs SET status='made_up' WHERE run_id=?", (RUN,))
    connection.commit()
    connection.close()
    with pytest.raises(PersistedRunDiagnosticsError, match="unknown persisted run state"):
        adapter.read_snapshot()

    connection = sqlite3.connect(db)
    connection.execute("UPDATE runs SET status='succeeded' WHERE run_id=?", (RUN,))
    connection.execute(
        "INSERT INTO task_attempts(task_run_id, model_task_id, attempt_number, status) VALUES (?, ?, ?, ?)",
        ("taskrun:orphan", "modeltask:orphan", 1, "succeeded"),
    )
    connection.commit()
    connection.close()
    with pytest.raises(PersistedRunDiagnosticsError, match="orphan task attempt"):
        adapter.read_snapshot()

    connection = sqlite3.connect(db)
    connection.execute("DELETE FROM task_attempts WHERE task_run_id='taskrun:orphan'")
    connection.execute(
        "INSERT INTO task_attempts(task_run_id, model_task_id, attempt_number, status) VALUES (?, ?, ?, ?)",
        ("taskrun:duplicate", rows[0]["logical_task_id"], 2, "succeeded"),
    )
    connection.commit()
    connection.close()
    with pytest.raises(PersistedRunDiagnosticsError, match="ambiguously repeated"):
        adapter.read_snapshot()

    connection = sqlite3.connect(db)
    connection.execute("DELETE FROM task_attempts WHERE task_run_id='taskrun:orphan'")
    connection.execute("DELETE FROM task_attempts WHERE task_run_id='taskrun:duplicate'")
    connection.execute("DELETE FROM provider_receipts")
    connection.commit()
    connection.close()
    with pytest.raises(PersistedRunDiagnosticsError, match="inconsistent receipt"):
        adapter.read_snapshot()

    cost_db = tmp_path / "cost-mismatch.sqlite3"
    cost_catalog, _, _ = _prepare_standard_run(cost_db)
    cost_catalog.close()
    cost_adapter = PersistedRunDiagnosticsAdapter(cost_db, RUN)
    connection = sqlite3.connect(cost_db)
    connection.execute("UPDATE cost_entries SET reservation_id='reservation:missing' WHERE entry_type='actual'")
    connection.commit()
    connection.close()
    with pytest.raises(PersistedRunDiagnosticsError, match="unknown reservation"):
        cost_adapter.read_snapshot()

