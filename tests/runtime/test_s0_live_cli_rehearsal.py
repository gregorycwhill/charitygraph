"""End-to-end provider-free rehearsal through the canonical S0 CLI."""
from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path

from charitygraph.runtime import SQLiteCatalog
from charitygraph.runtime.catalog import canonical_execution_configuration_hash
from charitygraph.s0_locator_discovery import freeze_locator_search_packet, prepare_locator_search_request
from charitygraph.scale_s0 import ExecutionAttemptIdentity, ScaleS0Preflight
from charitygraph.s0_pricing import load_supervisor_capture
from scripts.run_scale_s0 import main

from .test_s0_locator_search_lifecycle import _authority, _attempt, NOW, PROJECT


CAPTURE = Path(r"C:\Users\grego\My Drive\CharityGraph Agent Bridge\artifacts\openai-pricing-capture-2026-09-25.json")
CAPTURE_SHA = "d67304e32ee1f4760eefb7746eb8a849af19fee8b79beccd17578604a29a5e16"


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
        packet = freeze_locator_search_packet(mandate=mandate, execution_attempt=attempt, subject_abn=subject, query=f'"Locator {subject} {index}"', query_index=index,
                                              pricing=__import__("charitygraph.s0_locator_discovery", fromlist=["LocatorSearchPrice"]).LocatorSearchPrice(pricing_id, "0.10", "USD"), frozen_at=NOW.isoformat())
        ScaleS0Preflight.register_durable_packet(catalog, mandate, packet, execution_attempt_id=attempt.attempt_id)
        for bundle in __import__("charitygraph.s0_acquisition_bridge", fromlist=["bundle_packets"]).bundle_packets(mandate, (packet,), now=NOW, execution_attempt_id=attempt.attempt_id):
            catalog.register_scale_s0_physical_bundle(bundle.__dict__, execution_attempt_id=attempt.attempt_id)
        prepared = prepare_locator_search_request(packet=packet, reservation_id=f"reservation:rehearsal:{index}", provider_account_project=PROJECT, execution_authority="authority:rehearsal")
        request_material = {name: getattr(prepared.request, name) for name in prepared.request.__dataclass_fields__}
        request_material["route"] = request_material["route"].value
        work.append({"packet_id": packet.packet_id, "delivery_attempt_id": prepared.delivery_attempt_id, "client_request_id": prepared.client_request_id, "query": packet.locator_query, "request": request_material})
    catalog.close()
    return attempt, work


def test_three_item_cli_rehearsal_is_sequential_and_exactly_once(tmp_path, monkeypatch):
    snapshot = load_supervisor_capture(CAPTURE, expected_sha256=CAPTURE_SHA)
    db = tmp_path / "rehearsal.sqlite3"
    attempt, work = _make_catalog(db, ("11111111111", "11111111111", "11111111111"), snapshot.record_id)
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
            "--pricing-capture", str(CAPTURE), "--pricing-capture-sha256", CAPTURE_SHA, "--cohort-id", "cohort:locator", "--attested-by", "Greg",
            "--observed-at", now, "--setting-name", "Share inputs and outputs with OpenAI", "--observed-value", "Disabled", "--provider-project", PROJECT, "--execution-authority", "authority:rehearsal"]
    assert main(argv) == 0
    assert len(posts) == 3
    assert [item[0] for item in posts] == ["POST", "POST", "POST"]
    assert all(item[2].get("Openai-project") == PROJECT for item in posts)
    assert all(json.loads(item[3])["tool_choice"] == {"type": "web_search"} for item in posts)
    with SQLiteCatalog(db).open() as catalog:
        rows = catalog.list_provider_request_items(attempt.run_id)
        assert len(rows) == 3 and all(row["status"] == "completed" for row in rows)
        assert len({row["provider_request_item_id"] for row in rows}) == 3
        assert len({row["physical_attempt_id"] for row in rows}) == 3
        attempts = catalog.list_provider_request_attempts()
        assert len(attempts) == 3 and len({row["delivery_attempt_id"] for row in attempts}) == 3
        with catalog._connection() as conn:
            assert conn.execute("SELECT count(*) FROM cost_entries WHERE entry_type='actual'").fetchone()[0] == 3
            assert conn.execute("SELECT count(*) FROM cost_entries WHERE entry_type='reservation_release'").fetchone()[0] == 3
    assert main(argv) == 0
    assert len(posts) == 3
