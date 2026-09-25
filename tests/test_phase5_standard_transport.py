import hashlib
import io
import json
import socket
import ssl
import threading
import time
from pathlib import Path
from urllib.error import HTTPError
from urllib.error import URLError

import pytest

from charitygraph.phase5_standard_transport import (
    StandardCampaignCoordinator,
    StandardAmbiguous,
    OpenAIHTTPStandardClient,
    StandardProviderResponse,
    StandardTransportError,
    StandardSystemic,
    body_sha256,
    canonical_standard_body_bytes,
    client_request_id_for_physical_attempt,
    validate_client_request_id,
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

    def prepare_standard_transport_trace(self, attempt_id, **kwargs):
        return kwargs

    def mark_standard_send_started(self, attempt_id, *, client_request_id, now):
        with self._lock:
            self.started.append((attempt_id, client_request_id, now))

    def record_standard_transport_outcome(self, physical_attempt_id, **kwargs):
        return kwargs

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
        "physical_attempt_id": f"physicalattempt:{index:064x}",
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

    def create_response_once(self, body, *, client_request_id, request_started_at=None):
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
            if self.ambiguous_at == index or (isinstance(self.ambiguous_at, (set, tuple, list)) and index in self.ambiguous_at):
                raise StandardAmbiguous("synthetic connection loss")
            time.sleep(self.delay)
            response_body = {"id": f"resp_{index}", "status": "completed", "incomplete_details": None, "usage": {"input_tokens": 10, "output_tokens": 2}}
            raw = json.dumps(response_body, separators=(",", ":")).encode()
            return StandardProviderResponse(200, f"req_{index}", response_body, raw, client_request_id, f"req_{index}", "https://api.openai.com/v1/responses", request_started_at, True)
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


def test_cost_cap_cancelled_request_is_terminal_and_never_posted(tmp_path: Path):
    row = _row(19)
    catalog = FakeCatalog([row])
    catalog.items[row["provider_request_item_id"]]["status"] = "cancelled"
    provider = FakeProvider()
    result = StandardCampaignCoordinator(catalog=catalog, provider=provider, runtime_root=tmp_path).run([row])
    assert result["counts"] == {"replayed_terminal": 1}
    assert result["provider_posts"] == 0
    assert provider.posts == []


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


def test_first_ambiguous_crossing_is_quarantined_while_independent_attempts_continue(tmp_path: Path):
    rows = [_row(index) for index in range(20)]
    catalog = FakeCatalog(rows)
    for row in rows:
        catalog.items[row["provider_request_item_id"]]["attempt_id"] = row["delivery_attempt_id"]
    provider = FakeProvider(ambiguous_at=1)
    result = StandardCampaignCoordinator(catalog=catalog, provider=provider, runtime_root=tmp_path, max_concurrency=1).run(rows)

    assert result["stop_campaign"] is False
    assert result["unattempted"] == 0
    assert result["provider_posts"] == len(rows)
    assert result["ambiguous_crossings"] == 1


def test_second_ambiguous_crossing_trips_circuit_breaker(tmp_path: Path):
    rows = [_row(index) for index in range(8)]
    catalog = FakeCatalog(rows)
    for row in rows:
        catalog.items[row["provider_request_item_id"]]["attempt_id"] = row["delivery_attempt_id"]
    provider = FakeProvider(ambiguous_at={1, 2})
    result = StandardCampaignCoordinator(catalog=catalog, provider=provider, runtime_root=tmp_path, max_concurrency=1).run(rows)
    assert result["stop_campaign"] is True
    assert result["ambiguous_crossings"] == 2
    assert result["provider_posts"] == 2
    assert result["unattempted"] == 6


def test_unclassified_exception_after_post_is_quarantined_as_ambiguous(tmp_path: Path):
    row = _row(23)
    catalog = FakeCatalog([row])

    class CrashingProvider:
        calls = 0

        def create_response_once(self, body, *, client_request_id, request_started_at=None):
            self.calls += 1
            raise RuntimeError("unexpected transport interruption")

        def retrieve_response(self, response_id):
            raise AssertionError("must not retrieve or resend")

    provider = CrashingProvider()
    result = StandardCampaignCoordinator(catalog=catalog, provider=provider, runtime_root=tmp_path).run([row])
    assert result["counts"] == {"ambiguous": 1}
    assert result["stop_campaign"] is True
    assert result["provider_posts"] == 1
    assert provider.calls == 1
    assert catalog.failed[0][1]["ambiguous"] is True


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


@pytest.mark.parametrize("status", [401, 402, 403, 404, 408, 429, 500, 503])
def test_auth_budget_routing_and_systemic_http_failures_stop_campaign(monkeypatch, status):
    import charitygraph.phase5_standard_transport as transport

    def fail(*args, **kwargs):
        raise HTTPError("https://api.openai.com/v1/responses", status, "failure", {}, None)

    monkeypatch.setattr(transport, "urlopen", fail)
    monkeypatch.setenv("OPENAI_API_KEY", "test-only")
    with pytest.raises(StandardSystemic) as exc:
        OpenAIHTTPStandardClient(provider_account_project="proj_test").create_response_once(b"{}", client_request_id="cgpa-test")
    assert exc.value.status_code == status


def test_http_400_remains_a_definite_item_terminal_failure(monkeypatch):
    import charitygraph.phase5_standard_transport as transport
    raw = b'{"error":{"message":"bad request"}}'

    def fail(*args, **kwargs):
        raise HTTPError("https://api.openai.com/v1/responses", 400, "bad request", {"x-request-id": "req_test_terminal"}, io.BytesIO(raw))

    monkeypatch.setattr(transport, "urlopen", fail)
    monkeypatch.setenv("OPENAI_API_KEY", "test-only")
    with pytest.raises(StandardTransportError) as exc:
        OpenAIHTTPStandardClient(provider_account_project="proj_test").create_response_once(b"{}", client_request_id="cgpa-test")
    assert exc.value.systemic is False
    assert exc.value.status_code == 400
    assert exc.value.raw_bytes == raw
    assert exc.value.request_id == "req_test_terminal"


def test_client_request_id_is_stable_unique_ascii_and_bounded():
    first = client_request_id_for_physical_attempt("physicalattempt:one")
    assert first == client_request_id_for_physical_attempt("physicalattempt:one")
    assert first != client_request_id_for_physical_attempt("physicalattempt:two")
    assert first.isascii() and len(first) <= 512
    with pytest.raises(ValueError, match="ASCII"):
        validate_client_request_id("é")
    with pytest.raises(ValueError, match="512"):
        validate_client_request_id("a" * 513)


def test_openai_transport_sends_client_trace_and_retains_server_request_id(monkeypatch):
    import charitygraph.phase5_standard_transport as transport

    captured = {}

    class Response:
        status = 200
        headers = {"x-request-id": "req_server_123"}

        def __enter__(self):
            return self

        def __exit__(self, *_args):
            return False

        def read(self):
            return b'{"id":"resp_123","model":"gpt-5.6-luna","status":"completed"}'

    def fake_urlopen(request, timeout):
        captured["client_request_id"] = request.get_header("X-client-request-id")
        captured["authorization"] = request.get_header("Authorization")
        captured["timeout"] = timeout
        return Response()

    monkeypatch.setattr(transport, "urlopen", fake_urlopen)
    monkeypatch.setenv("OPENAI_API_KEY", "test-only-secret")
    response = OpenAIHTTPStandardClient(provider_account_project="proj_test").create_response_once(b"{}", client_request_id="cgpa-test-trace", request_started_at="2026-09-13T10:00:00+00:00")
    assert captured["client_request_id"] == "cgpa-test-trace"
    assert captured["authorization"] == "Bearer test-only-secret"
    assert captured["timeout"] == transport.STANDARD_SOCKET_TIMEOUT_SECONDS == 300
    assert response.client_request_id == "cgpa-test-trace"
    assert response.server_request_id == "req_server_123"
    assert response.endpoint == "https://api.openai.com/v1/responses"
    assert response.request_started_at == "2026-09-13T10:00:00+00:00"
    assert response.response_headers_received is True
    assert response.elapsed_seconds is not None and response.elapsed_seconds >= 0


def test_ambiguous_transport_retains_trace_without_claiming_response_headers(monkeypatch):
    import charitygraph.phase5_standard_transport as transport

    calls = []
    def fail(_request, timeout):
        calls.append(timeout)
        raise URLError("synthetic socket timeout")

    monkeypatch.setattr(transport, "urlopen", fail)
    monkeypatch.setenv("OPENAI_API_KEY", "test-only-secret")
    with pytest.raises(StandardAmbiguous) as exc:
        OpenAIHTTPStandardClient(provider_account_project="proj_test").create_response_once(b"{}", client_request_id="cgpa-ambiguous-trace", request_started_at="2026-09-13T10:00:00+00:00")
    assert exc.value.client_request_id == "cgpa-ambiguous-trace"
    assert exc.value.endpoint == "https://api.openai.com/v1/responses"
    assert exc.value.request_started_at == "2026-09-13T10:00:00+00:00"
    assert exc.value.response_headers_received is False
    assert exc.value.request_id is None
    assert calls == [300]


@pytest.mark.parametrize(("error", "state", "ambiguous"), [
    (socket.gaierror(-2, "name lookup failed"), "DNS_FAILURE", False),
    (ConnectionRefusedError(111, "connection refused"), "CONNECT_FAILURE", False),
    (PermissionError(10013, "socket access denied"), "LOCAL_SOCKET_PERMISSION_DENIED", False),
    (ssl.SSLError("TLS handshake failed"), "TLS_SETUP_FAILURE", False),
    (TimeoutError("timed out"), "SOCKET_TIMEOUT_PHASE_UNKNOWN", True),
    (ConnectionResetError(104, "connection reset"), "REMOTE_DISCONNECT_OR_WRITE_FAILURE", True),
])
def test_transport_exception_classification_preserves_nested_cause(monkeypatch, error, state, ambiguous):
    import charitygraph.phase5_standard_transport as transport
    if isinstance(error, PermissionError):
        error.winerror = 10013

    def fail(_request, timeout):
        raise URLError(error)

    monkeypatch.setattr(transport, "urlopen", fail)
    monkeypatch.setenv("OPENAI_API_KEY", "test-only")
    with pytest.raises(StandardTransportError) as caught:
            OpenAIHTTPStandardClient(provider_account_project="proj_test").create_response_once(b"{}", client_request_id="cgpa-classify")
    assert caught.value.transport_state == state
    assert caught.value.ambiguous is ambiguous
    assert caught.value.cause_type == type(error).__name__
    assert caught.value.elapsed_seconds is not None
    assert type(error).__name__ in str(caught.value)


def test_models_get_is_single_authenticated_traceable_non_generation_request(monkeypatch):
    import charitygraph.phase5_standard_transport as transport

    calls = []

    class Response:
        status = 200
        headers = {"x-request-id": "req_models_test"}

        def __enter__(self):
            return self

        def __exit__(self, *_args):
            return False

        def read(self):
            return b'{"data":[]}'

    def fake_urlopen(request, timeout):
        calls.append((request.full_url, request.get_method(), request.get_header("X-client-request-id"), request.get_header("Authorization"), timeout))
        return Response()

    monkeypatch.setattr(transport, "urlopen", fake_urlopen)
    monkeypatch.setenv("OPENAI_API_KEY", "test-only")
    status, headers, raw, elapsed = OpenAIHTTPStandardClient(provider_account_project="proj_test").list_models_once(client_request_id="cgpa-models-test")
    assert status == 200 and headers.get("x-request-id") == "req_models_test"
    assert raw == b'{"data":[]}' and elapsed >= 0
    assert calls == [("https://api.openai.com/v1/models", "GET", "cgpa-models-test", "Bearer test-only", 300)]
    assert not isinstance((status, headers, raw, elapsed), StandardProviderResponse)


def test_read_failure_after_http_headers_is_not_called_ambiguous_or_rejected(monkeypatch):
    import charitygraph.phase5_standard_transport as transport

    class Response:
        status = 200
        headers = {"x-request-id": "req_headers_arrived"}
        def __enter__(self): return self
        def __exit__(self, *_args): return False
        def read(self): raise TimeoutError("response body stalled")

    monkeypatch.setattr(transport, "urlopen", lambda *_args, **_kwargs: Response())
    monkeypatch.setenv("OPENAI_API_KEY", "test-only")
    with pytest.raises(StandardSystemic) as caught:
            OpenAIHTTPStandardClient(provider_account_project="proj_test").create_response_once(b"{}", client_request_id="cgpa-body-read")
    assert caught.value.transport_state == "PROVIDER_RESPONSE_BODY_READ_FAILURE"
    assert caught.value.status_code == 200
    assert caught.value.request_id == "req_headers_arrived"
    assert caught.value.response_headers_received is True
    assert caught.value.ambiguous is False


def test_unparseable_http_response_is_recorded_as_response_body_failure(monkeypatch):
    import charitygraph.phase5_standard_transport as transport

    class Response:
        status = 200
        headers = {"x-request-id": "req_invalid_body"}
        def __enter__(self): return self
        def __exit__(self, *_args): return False
        def read(self): return b"not-json"

    monkeypatch.setattr(transport, "urlopen", lambda *_args, **_kwargs: Response())
    monkeypatch.setenv("OPENAI_API_KEY", "test-only")
    with pytest.raises(StandardSystemic) as caught:
            OpenAIHTTPStandardClient(provider_account_project="proj_test").create_response_once(b"{}", client_request_id="cgpa-body-parse")
    assert caught.value.transport_state == "PROVIDER_RESPONSE_BODY_PARSE_FAILURE"
    assert caught.value.status_code == 200
    assert caught.value.raw_bytes == b"not-json"
    assert caught.value.response_headers_received is True
