import io
import json
from urllib.error import HTTPError

import pytest

from charitygraph.openai_client import OpenAIRequestError, _post, responses_create


def _raw():
    return {"id": "resp:test", "model": "gpt-5.6-luna", "status": "completed", "output_text": "{}", "usage": {"input_tokens": 3, "output_tokens": 2, "total_tokens": 5}}


def test_success_reports_one_transport_request(monkeypatch):
    monkeypatch.setattr("charitygraph.openai_client._post", lambda *args, **kwargs: _raw())
    result = responses_create(model="gpt-5.6-luna", input_text="x", text_format={"type": "json_schema"}, max_attempts=2)
    assert result.transport_requests == 1


def test_retry_success_reports_two_transport_requests(monkeypatch):
    calls = []
    def fake_post(*args, **kwargs):
        calls.append(1)
        if len(calls) == 1:
            raise OpenAIRequestError("temporary")
        return _raw()
    monkeypatch.setattr("charitygraph.openai_client._post", fake_post)
    monkeypatch.setattr("charitygraph.openai_client.time.sleep", lambda _: None)
    result = responses_create(model="gpt-5.6-luna", input_text="x", text_format={"type": "json_schema"}, max_attempts=2)
    assert result.transport_requests == 2
    assert len(calls) == 2


def test_exhausted_transport_error_reports_attempts_without_payload(monkeypatch):
    def fake_post(*args, **kwargs):
        raise OpenAIRequestError("temporary")
    monkeypatch.setattr("charitygraph.openai_client._post", fake_post)
    monkeypatch.setattr("charitygraph.openai_client.time.sleep", lambda _: None)
    with pytest.raises(OpenAIRequestError) as exc:
        responses_create(model="gpt-5.6-luna", input_text="x", text_format={"type": "json_schema"}, max_attempts=2)
    assert exc.value.attempts_made == 2
    assert "temporary" in str(exc.value)


def test_http_400_is_non_retryable(monkeypatch):
    calls = []
    def fake_post(*args, **kwargs):
        calls.append(1)
        raise OpenAIRequestError("invalid request", status_code=400)
    monkeypatch.setattr("charitygraph.openai_client._post", fake_post)
    with pytest.raises(OpenAIRequestError) as exc:
        responses_create(model="gpt-5.6-luna", input_text="x", text_format={"type": "json_schema"}, max_attempts=2)
    assert exc.value.attempts_made == 1
    assert len(calls) == 1


def test_structured_http_error_retains_only_safe_bounded_fields(monkeypatch):
    body = json.dumps({"error": {"type": "invalid_request_error", "code": "schema", "param": "text.format", "message": "bad schema"}}).encode()
    error = HTTPError("https://api.openai.com/v1/responses", 400, "bad", {}, io.BytesIO(body))
    monkeypatch.setattr("charitygraph.openai_client.urlopen", lambda *args, **kwargs: (_ for _ in ()).throw(error))
    monkeypatch.setenv("OPENAI_API_KEY", "test-secret")
    with pytest.raises(OpenAIRequestError) as exc:
        _post("/responses", {})
    assert exc.value.diagnostic.as_dict() == {"status_code": 400, "error_type": "invalid_request_error", "error_code": "schema", "error_param": "text.format", "error_message": "bad schema"}


def test_structured_error_redacts_token_like_material(monkeypatch):
    body = json.dumps({"error": {"message": "Bearer sk-abcdefghijklmnopqrstuvwxyz0123456789"}}).encode()
    error = HTTPError("https://api.openai.com/v1/responses", 400, "bad", {}, io.BytesIO(body))
    monkeypatch.setattr("charitygraph.openai_client.urlopen", lambda *args, **kwargs: (_ for _ in ()).throw(error))
    monkeypatch.setenv("OPENAI_API_KEY", "test-secret")
    with pytest.raises(OpenAIRequestError) as exc:
        _post("/responses", {})
    assert "sk-abcdefghijklmnopqrstuvwxyz" not in str(exc.value)
    assert "Bearer [redacted]" in str(exc.value)


def test_malformed_http_error_has_generic_safe_diagnostic(monkeypatch):
    error = HTTPError("https://api.openai.com/v1/responses", 400, "bad", {}, io.BytesIO(b"not-json"))
    monkeypatch.setattr("charitygraph.openai_client.urlopen", lambda *args, **kwargs: (_ for _ in ()).throw(error))
    monkeypatch.setenv("OPENAI_API_KEY", "test-secret")
    with pytest.raises(OpenAIRequestError) as exc:
        _post("/responses", {})
    assert exc.value.diagnostic.as_dict() == {"status_code": 400}
