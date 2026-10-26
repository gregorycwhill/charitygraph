from __future__ import annotations

import copy
import json
import sqlite3
from pathlib import Path

import pytest

from charitygraph.phase5_run_diagnostics import (
    NOT_OBSERVED,
    RunDiagnosticsError,
    canonical_diagnostics_json,
    diagnostics_sha256,
    project_run_diagnostics,
)
from charitygraph.phase5_standard_transport import StandardCampaignCoordinator

from test_phase5_standard_transport import FakeCatalog, FakeProvider, _row


def _result(item_id: str, status: str, *, subject: str = "subject-a", scope: str = "scope-a", posts: int = 0, stop: bool = False) -> dict:
    return {
        "item_id": item_id,
        "subject_id": subject,
        "scope_id": scope,
        "status": status,
        "provider_posts": posts,
        "stop_campaign": stop,
    }


def _ledger(*, reservations=None, entries=None, tasks=None, attempts=None, receipts=None) -> dict:
    return {
        "tasks": [] if tasks is None else tasks,
        "attempts": [] if attempts is None else attempts,
        "receipts": [] if receipts is None else receipts,
        "reservations": [] if reservations is None else reservations,
        "cost_entries": [] if entries is None else entries,
    }


def _run(results, **extra) -> dict:
    value = {
        "run_id": "run:diagnostic-test",
        "provenance": {"run_record_ref": "run-record:fixture-1", "ledger_snapshot_ref": "ledger:fixture-1"},
        "results": results,
        "planned_item_count": len(results),
        "configured_concurrency": 2,
        "observed_concurrency": 1,
        "stop_campaign": False,
    }
    value.update(extra)
    return value


def test_canonical_representation_version_and_hash_are_byte_stable():
    first = _run(
        [_result("item:b", "completed", posts=1), _result("item:a", "replayed_terminal")],
        planned_item_count=2,
    )
    first["provider_posts"] = 1
    second = {
        "stop_campaign": False,
        "observed_concurrency": 1,
        "configured_concurrency": 2,
        "planned_item_count": 2,
        "results": [
            {"scope_id": "scope-a", "subject_id": "subject-a", "provider_posts": 1, "status": "completed", "stop_campaign": False, "item_id": "item:b"},
            {"scope_id": "scope-a", "subject_id": "subject-a", "provider_posts": 0, "status": "replayed_terminal", "stop_campaign": False, "item_id": "item:a"},
        ],
        "provenance": {"ledger_snapshot_ref": "ledger:fixture-1", "run_record_ref": "run-record:fixture-1"},
        "provider_posts": 1,
        "run_id": "run:diagnostic-test",
    }
    left = project_run_diagnostics(first, _ledger())
    right = project_run_diagnostics(second, _ledger())
    assert left.document["schema"] == "charitygraph.phase5.run-diagnostics/v1"
    assert left.document["schema_version"] == 1
    assert left.canonical_json == right.canonical_json
    assert left.sha256 == right.sha256 == diagnostics_sha256(left)
    assert left.sha256 == diagnostics_sha256(json.loads(left.canonical_json))
    assert canonical_diagnostics_json(left) == left.canonical_json


def test_summary_counts_stops_unattempted_concurrency_and_posts_without_invention():
    projection = project_run_diagnostics(
        _run(
            [
                _result("item:1", "completed", posts=1),
                _result("item:2", "failed_terminal"),
                _result("item:3", "replayed_terminal"),
            ],
            planned_item_count=5,
            provider_posts=1,
            observed_concurrency=2,
        ),
        _ledger(),
    )
    summary = projection.document["summary"]
    assert summary["status_counts"] == {"completed": 1, "failed_terminal": 1, "replayed_terminal": 1}
    assert summary["unattempted"] == 2
    assert summary["provider_posts"] == summary["new_provider_posts"] == 1
    assert summary["concurrency"] == {"configured": 2, "observed_max": 2, "cap_respected": True}
    assert summary["stop"] == {
        "campaign_stopped": False,
        "classification": "none",
        "stop_item_count": 0,
        "ambiguous_crossings": 0,
        "terminal_item_failures": 1,
    }
    assert projection.document["ledger"]["record_counts"] == {"tasks": 0, "attempts": 0, "receipts": 0, "reservations": 0, "cost_entries": 0}


def test_real_fake_standard_run_respects_cap_and_keeps_peer_progress(tmp_path: Path):
    rows = [_row(index) for index in range(8)]
    catalog = FakeCatalog(rows)
    for row in rows:
        catalog.items[row["provider_request_item_id"]]["attempt_id"] = row["delivery_attempt_id"]
    result = StandardCampaignCoordinator(
        catalog=catalog,
        provider=FakeProvider(terminal_at=2),
        runtime_root=tmp_path,
        max_concurrency=3,
    ).run(rows)
    enriched = []
    for item in result["results"]:
        enriched.append({**item, "item_id": item["request_item_id"], "subject_id": "subject-" + item["request_item_id"].split(":")[-1], "scope_id": "scope-standard"})
    projection = project_run_diagnostics(
        _run(enriched, planned_item_count=8, configured_concurrency=3, observed_concurrency=result["max_observed_concurrency"], provider_posts=result["provider_posts"]),
        _ledger(),
    )
    assert result["max_observed_concurrency"] <= 3
    assert projection.document["summary"]["concurrency"]["cap_respected"] is True
    assert projection.document["summary"]["status_counts"]["failed_terminal"] == 1
    assert projection.document["summary"]["items_observed"] == 8
    assert projection.document["summary"]["unattempted"] == 0
    assert len(projection.document["subjects"]) == 8


def test_saved_response_restart_has_zero_new_provider_posts(tmp_path: Path):
    row = _row(77)
    catalog = FakeCatalog([row])
    catalog.items[row["provider_request_item_id"]]["status"] = "submitted"
    catalog.items[row["provider_request_item_id"]]["attempt_id"] = row["delivery_attempt_id"]
    result_dir = tmp_path / "standard-results"
    result_dir.mkdir()
    raw_path = result_dir / (row["provider_request_item_id"].replace(":", "_") + ".json")
    raw = {"id": "resp_saved", "status": "completed", "incomplete_details": None, "usage": {"input_tokens": 3, "output_tokens": 1}}
    raw_path.write_text(json.dumps(raw), encoding="utf-8")
    raw_path.with_suffix(".meta.json").write_text(json.dumps({"status_code": 200, "request_id": "req_saved"}), encoding="utf-8")
    result = StandardCampaignCoordinator(catalog=catalog, provider=FakeProvider(), runtime_root=tmp_path).run([row])
    item = {**result["results"][0], "item_id": result["results"][0]["request_item_id"], "subject_id": "subject-restart", "scope_id": "scope-restart"}
    projection = project_run_diagnostics(_run([item], planned_item_count=1, provider_posts=0, restart_no_resend=True), _ledger())
    assert result["provider_posts"] == 0
    assert projection.document["summary"]["new_provider_posts"] == 0
    assert projection.document["summary"]["restart_no_resend"] is True
    assert projection.document["summary"]["status_counts"] == {"completed": 1}


def test_ambiguous_and_systemic_stops_remain_distinct():
    ambiguous = project_run_diagnostics(
        _run([_result("item:a", "ambiguous", posts=1, stop=True)], planned_item_count=3, stop={"campaign_stopped": True, "classification": "ambiguous"}),
        _ledger(),
    )
    systemic = project_run_diagnostics(
        _run([_result("item:s", "failed_pre_send", stop=True)], planned_item_count=3, stop={"campaign_stopped": True, "classification": "systemic"}),
        _ledger(),
    )
    assert ambiguous.document["summary"]["stop"]["classification"] == "ambiguous"
    assert ambiguous.document["summary"]["stop"]["ambiguous_crossings"] == 1
    assert systemic.document["summary"]["stop"]["classification"] == "systemic"
    assert systemic.document["summary"]["stop"]["ambiguous_crossings"] == 0
    assert ambiguous.document["summary"]["stop"] != systemic.document["summary"]["stop"]


def test_sqlite_ledger_reconciles_once_and_detects_discrepancy_and_double_counting(tmp_path: Path):
    connection = sqlite3.connect(tmp_path / "ledger.sqlite3")
    connection.row_factory = sqlite3.Row
    connection.executescript("""
        CREATE TABLE tasks (task_id TEXT);
        CREATE TABLE attempts (attempt_id TEXT);
        CREATE TABLE receipts (receipt_id TEXT);
        CREATE TABLE reservations (reservation_id TEXT, reserved_aud TEXT, currency TEXT, status TEXT);
        CREATE TABLE cost_entries (entry_key TEXT, reservation_id TEXT, entry_type TEXT, accounting_amount TEXT, accounting_currency TEXT);
    """)
    connection.execute("INSERT INTO tasks VALUES ('task:1')")
    connection.execute("INSERT INTO attempts VALUES ('attempt:1')")
    connection.execute("INSERT INTO receipts VALUES ('receipt:1')")
    connection.execute("INSERT INTO reservations VALUES ('reservation:1', '0.010000', 'AUD', 'released')")
    connection.executemany("INSERT INTO cost_entries VALUES (?, ?, ?, ?, ?)", [
        ("actual:1", "reservation:1", "actual", "0.002000", "AUD"),
        ("release:1", "reservation:1", "reservation_release", "0.008000", "AUD"),
    ])
    connection.commit()
    read = lambda table: [dict(row) for row in connection.execute(f"SELECT * FROM {table} ORDER BY 1").fetchall()]
    ledger = _ledger(tasks=read("tasks"), attempts=read("attempts"), receipts=read("receipts"), reservations=read("reservations"), entries=read("cost_entries"))
    run = _run([_result("item:1", "completed", posts=1)], planned_item_count=1, provider_posts=1)
    projection = project_run_diagnostics(run, ledger)
    reconciliation = projection.document["ledger"]["reconciliation"]
    assert reconciliation["state"] == "RECONCILED"
    assert reconciliation["discrepancy"] == "0"
    assert reconciliation["positions"][0]["actual"] == "0.002"
    assert reconciliation["positions"][0]["released"] == "0.008"
    assert projection.document["ledger"]["actuals"] == "0.002"
    assert projection.document["ledger"]["releases"] == "0.008"

    duplicate = copy.deepcopy(ledger)
    duplicate["cost_entries"].append(dict(duplicate["cost_entries"][0]))
    with pytest.raises(RunDiagnosticsError, match="double count"):
        project_run_diagnostics(run, duplicate)
    discrepancy = copy.deepcopy(ledger)
    discrepancy["cost_entries"][1]["accounting_amount"] = "0.007000"
    assert project_run_diagnostics(run, discrepancy).document["ledger"]["reconciliation"]["state"] == "INCOMPLETE_OR_DISCREPANT"
    assert connection.execute("SELECT COUNT(*) FROM cost_entries").fetchone()[0] == 2
    connection.close()


def test_malformed_omitted_and_conflicting_input_fails_closed_without_mutation():
    ledger = _ledger(
        tasks=[{"task_id": "task:1"}],
        attempts=[{"attempt_id": "attempt:1"}],
        receipts=[{"receipt_id": "receipt:1"}],
        reservations=[{"reservation_id": "reservation:1", "reserved_aud": "0.010", "currency": "AUD"}],
        entries=[{"entry_key": "actual:1", "reservation_id": "reservation:1", "entry_type": "actual", "accounting_amount": "0.002", "accounting_currency": "AUD"}],
    )
    before = copy.deepcopy(ledger)
    with pytest.raises(RunDiagnosticsError):
        project_run_diagnostics({"run_id": "run:bad"}, ledger)
    with pytest.raises(RunDiagnosticsError, match="conflicts"):
        project_run_diagnostics(_run([_result("item:1", "completed", posts=1)], provider_posts=0), ledger)
    with pytest.raises(RunDiagnosticsError, match="exceeds"):
        project_run_diagnostics(_run([_result("item:1", "completed")], configured_concurrency=1, observed_concurrency=2), ledger)
    assert ledger == before
    assert NOT_OBSERVED not in project_run_diagnostics(_run([_result("item:1", "completed")]), _ledger()).document["summary"]["status_counts"]
