import hashlib
import json
import threading
import time
from pathlib import Path

from charitygraph.phase5_standard_transport import (
    StandardCampaignCoordinator,
    StandardAmbiguous,
    StandardProviderResponse,
    StandardTransportError,
    StandardSystemic,
    body_sha256,
    canonical_standard_body_bytes,
)


class FakeCatalog:
    def __init__(self, rows):
        self.items = {row["provider_request_item_id"]: {"status": "prepared"} for row in rows}
        self.started = []
        self.completed = []
        self.failed = []
        self._lock = threading.Lock()

    def get_provider_request_item(self, request_id):
        return self.items.get(request_id)

    def mark_standard_send_started(self, attempt_id, *, now):
        with self._lock:
            self.started.append(attempt_id)

    def complete_standard_delivery(self, attempt_id, **kwargs):
        with self._lock:
            self.completed.append((attempt_id, kwargs))
            request_id = next(key for key, row in self.items.items() if row.get("attempt_id") == attempt_id) if any(row.get("attempt_id") == attempt_id for row in self.items.values()) else None
            if request_id is not None:
                self.items[request_id]["status"] = "completed"

    def settle_standard_failure(self, attempt_id, **kwargs):
        with self._lock:
            self.failed.append((attempt_id, kwargs))


def _row(index: int, *, terminal=False, schema_name="program_service_discovery_v2"):
    request_id = f"requestitem:{index:064x}"
    schema = {"type": "object", "properties": {"proposals": {"type": "array"}}, "required": ["proposals"], "additionalProperties": False}
    body = {
        "model": "gpt-5.6-luna",
        "reasoning": {"effort": "low"},
        "max_output_tokens": 8000,
        "store": False,
        "input": [{"role": "user", "content": [{"type": "input_text", "text": "évidence — stable"}]}],
        "text": {"format": {"type": "json_schema", "name": schema_name, "strict": True, "schema": schema}},
        "metadata": {"logical_task_id": f"modeltask:{index:064x}", "semantic_contract_hash": "c" * 64},
    }
    raw = canonical_standard_body_bytes(body)
    return {
        "provider_request_item_id": request_id,
        "delivery_attempt_id": f"deliveryattempt:{index:064x}",
        "delivery_mode": "standard",
        "model": "gpt-5.6-luna",
        "reasoning_effort": "low",
        "provider_schema_name": schema_name,
        "provider_service_tier": None,
        "max_output_tokens": 8000,
        "logical_task_id": f"modeltask:{index:064x}",
        "semantic_contract_hash": "c" * 64,
        "schema_hash": hashlib.sha256(json.dumps(schema, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode()).hexdigest(),
        "request_body": body,
        "request_body_sha256": body_sha256(raw),
        "terminal": terminal,
    }


class FakeProvider:
    def __init__(self, *, delay=0.001, systemic_at=None, terminal_at=None, ambiguous_at=None):
        self.delay = delay
        self.systemic_at = systemic_at
        self.terminal_at = terminal_at
        self.ambiguous_at = ambiguous_at
        self.posts = []
        self.active = 0
        self.max_active = 0
        self._lock = threading.Lock()

    def create_response_once(self, body):
        with self._lock:
            self.posts.append(body)
            index = len(self.posts)
            self.active += 1
            self.max_active = max(self.max_active, self.active)
        try:
            if self.systemic_at == index:
                raise StandardSystemic("synthetic rate limit")
            if self.terminal_at == index:
                raise StandardTransportError("synthetic item failure")
            if self.ambiguous_at == index:
                raise StandardAmbiguous("synthetic connection loss")
            time.sleep(self.delay)
            response_body = {"id": f"resp_{index}", "status": "completed", "incomplete_details": None, "usage": {"input_tokens": 10, "output_tokens": 2}}
            raw = json.dumps(response_body, separators=(",", ":")).encode()
            return StandardProviderResponse(200, f"req_{index}", response_body, raw)
        finally:
            with self._lock:
                self.active -= 1

    def retrieve_response(self, response_id):
        raise AssertionError("replay must not retrieve a terminal response")


def test_exact_utf8_body_and_93_item_provider_free_rehearsal(tmp_path: Path):
    rows = [_row(index) for index in range(93)]
    catalog = FakeCatalog(rows)
    for row in rows:
        catalog.items[row["provider_request_item_id"]]["attempt_id"] = row["delivery_attempt_id"]
    provider = FakeProvider()
    result = StandardCampaignCoordinator(catalog=catalog, provider=provider, runtime_root=tmp_path, max_concurrency=4).run(rows)

    assert result["counts"] == {"completed": 93}
    assert result["provider_posts"] == 93
    assert result["unattempted"] == 0
    assert result["max_observed_concurrency"] <= 4
    assert provider.max_active <= 4
    assert all(b"\xc3\xa9vidence" in body for body in provider.posts)
    assert len([path for path in (tmp_path / "standard-results").glob("*.json") if not path.name.endswith(".meta.json")]) == 93


def test_terminal_replay_is_noop_and_does_not_post(tmp_path: Path):
    row = _row(1)
    catalog = FakeCatalog([row])
    catalog.items[row["provider_request_item_id"]]["status"] = "completed"
    provider = FakeProvider()
    result = StandardCampaignCoordinator(catalog=catalog, provider=provider, runtime_root=tmp_path).run([row])

    assert result["counts"] == {"replayed_terminal": 1}
    assert result["provider_posts"] == 0


def test_saved_response_reconciles_without_post(tmp_path: Path):
    row = _row(2)
    catalog = FakeCatalog([row])
    catalog.items[row["provider_request_item_id"]]["status"] = "submitted"
    catalog.items[row["provider_request_item_id"]]["attempt_id"] = row["delivery_attempt_id"]
    result_dir = tmp_path / "standard-results"
    result_dir.mkdir()
    raw_path = result_dir / (row["provider_request_item_id"].replace(":", "_") + ".json")
    # Keep the exact provider body as the durable raw artifact and a small
    # sidecar for transport metadata that is not part of the response JSON.
    response_body = {"id": "resp_saved", "status": "completed", "incomplete_details": None, "usage": {"input_tokens": 3, "output_tokens": 1}}
    raw_path.write_bytes(json.dumps(response_body, separators=(",", ":")).encode())
    raw_path.with_suffix(".meta.json").write_text(json.dumps({"status_code": 200, "request_id": "req_saved"}), encoding="utf-8")
    provider = FakeProvider()
    result = StandardCampaignCoordinator(catalog=catalog, provider=provider, runtime_root=tmp_path).run([row])

    assert result["counts"] == {"completed": 1}
    assert result["provider_posts"] == 0


def test_systemic_failure_stops_feeder_without_resending(tmp_path: Path):
    rows = [_row(index) for index in range(20)]
    catalog = FakeCatalog(rows)
    for row in rows:
        catalog.items[row["provider_request_item_id"]]["attempt_id"] = row["delivery_attempt_id"]
    provider = FakeProvider(systemic_at=1)
    result = StandardCampaignCoordinator(catalog=catalog, provider=provider, runtime_root=tmp_path, max_concurrency=4).run(rows)

    assert result["stop_campaign"] is True
    assert result["unattempted"] > 0
    assert result["provider_posts"] <= 4


def test_item_terminal_failure_does_not_stop_independent_items(tmp_path: Path):
    rows = [_row(index) for index in range(20)]
    catalog = FakeCatalog(rows)
    for row in rows:
        catalog.items[row["provider_request_item_id"]]["attempt_id"] = row["delivery_attempt_id"]
    result = StandardCampaignCoordinator(catalog=catalog, provider=FakeProvider(terminal_at=5), runtime_root=tmp_path, max_concurrency=4).run(rows)

    assert result["stop_campaign"] is False
    assert result["provider_posts"] == 20
    assert result["counts"].get("failed_terminal") == 1
    assert result["counts"].get("completed") == 19


def test_ambiguous_send_holds_and_does_not_resend(tmp_path: Path):
    rows = [_row(index) for index in range(20)]
    catalog = FakeCatalog(rows)
    for row in rows:
        catalog.items[row["provider_request_item_id"]]["attempt_id"] = row["delivery_attempt_id"]
    provider = FakeProvider(ambiguous_at=1)
    result = StandardCampaignCoordinator(catalog=catalog, provider=provider, runtime_root=tmp_path, max_concurrency=4).run(rows)

    assert result["stop_campaign"] is True
    assert result["unattempted"] > 0
    assert result["provider_posts"] <= 4


def test_reconciliation_callback_runs_after_durable_success(tmp_path: Path):
    row = _row(9)
    catalog = FakeCatalog([row])
    catalog.items[row["provider_request_item_id"]]["attempt_id"] = row["delivery_attempt_id"]
    calls = []
    result = StandardCampaignCoordinator(catalog=catalog, provider=FakeProvider(), runtime_root=tmp_path, on_reconciled=lambda *args: calls.append(args)).run([row])

    assert result["counts"] == {"completed": 1}
    assert len(calls) == 1
    assert calls[0][2] == {"input_tokens": 10, "output_tokens": 2}


def test_failed_and_ambiguous_terminal_replays_are_noop(tmp_path: Path):
    for status in ("failed", "send_ambiguous"):
        row = _row(20 if status == "failed" else 21)
        catalog = FakeCatalog([row])
        catalog.items[row["provider_request_item_id"]]["status"] = status
        provider = FakeProvider()
        result = StandardCampaignCoordinator(catalog=catalog, provider=provider, runtime_root=tmp_path).run([row])
        assert result["counts"] == {"replayed_terminal": 1}
        assert result["provider_posts"] == 0


def test_pinned_schema_or_body_drift_fails_before_post(tmp_path: Path):
    row = _row(7)
    row["request_body"]["text"]["format"]["name"] = "wrong"
    catalog = FakeCatalog([row])
    provider = FakeProvider()
    result = StandardCampaignCoordinator(catalog=catalog, provider=provider, runtime_root=tmp_path).run([row])

    assert result["counts"] == {"failed_pre_send": 1}
    assert result["provider_posts"] == 0


def test_mandate_proof_failure_blocks_provider_boundary(tmp_path: Path):
    row = _row(8)
    catalog = FakeCatalog([row])
    provider = FakeProvider()
    result = StandardCampaignCoordinator(catalog=catalog, provider=provider, runtime_root=tmp_path, mandate_evaluator=lambda _: type("Decision", (), {"authorized": False})()).run([row])

    assert result["counts"] == {"failed_pre_send": 1}
    assert result["provider_posts"] == 0


def test_standard_transport_pins_any_explicit_schema_name(tmp_path: Path):
    row = _row(22, schema_name="direct_service_semantics_v1")
    catalog = FakeCatalog([row])
    catalog.items[row["provider_request_item_id"]]["attempt_id"] = row["delivery_attempt_id"]
    result = StandardCampaignCoordinator(catalog=catalog, provider=FakeProvider(), runtime_root=tmp_path).run([row])
    assert result["counts"] == {"completed": 1}
