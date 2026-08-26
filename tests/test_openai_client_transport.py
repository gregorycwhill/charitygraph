import io
import json
from urllib.error import HTTPError

import pytest

import charitygraph.openai_client as client


def test_http_error_retains_only_safe_structured_diagnostics():
    body = json.dumps({"error": {"type": "invalid_request_error", "code": "invalid_schema", "param": "text.format", "message": "schema is invalid", "secret": "do-not-retain"}, "request": "do-not-retain"}).encode()
    error = HTTPError("https://api.openai.com/v1/responses", 400, "Bad Request", {}, io.BytesIO(body))
    safe = client._safe_error(error)
    assert safe.status_code == 400
    assert safe.diagnostics == {"status": 400, "type": "invalid_request_error", "code": "invalid_schema", "param": "text.format", "message": "schema is invalid"}
    assert safe.retryable is False
    assert "do-not-retain" not in str(safe)


def test_http_400_is_not_retried(monkeypatch):
    calls = []

    def fail(*args, **kwargs):
        calls.append(1)
        raise client.OpenAIRequestError("bad request", status_code=400, diagnostics={"status": 400}, retryable=False)

    monkeypatch.setattr(client, "_post", fail)
    with pytest.raises(client.OpenAIRequestError):
        client.responses_create(model="gpt-5.6-luna", input_text="synthetic", text_format={"type": "json_schema"})
    assert len(calls) == 1


def test_transient_5xx_keeps_one_bounded_retry(monkeypatch):
    calls = []

    def fail(*args, **kwargs):
        calls.append(1)
        raise client.OpenAIRequestError("server", status_code=500, diagnostics={"status": 500}, retryable=True)

    monkeypatch.setattr(client, "_post", fail)
    monkeypatch.setattr(client.time, "sleep", lambda _: None)
    with pytest.raises(client.OpenAIRequestError):
        client.responses_create(model="gpt-5.6-luna", input_text="synthetic", text_format={"type": "json_schema"})
    assert len(calls) == 2