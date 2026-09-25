import io
import json

import pytest

from charitygraph.phase5_standard_transport import OpenAIHTTPStandardClient, StandardSystemic


class _Response:
    status = 200
    headers = {"x-request-id": "req-test"}
    def __enter__(self): return self
    def __exit__(self, *_): return None
    def read(self): return json.dumps({"id": "resp-test", "model": "gpt-5.6-luna", "status": "completed", "output": [], "usage": {"input_tokens": 1, "output_tokens": 1}}).encode()


def test_standard_post_sends_bound_project_without_persisting_key(monkeypatch):
    captured = {}
    def fake(request, **kwargs):
        captured.update(dict(request.header_items()))
        return _Response()
    monkeypatch.setattr("charitygraph.phase5_standard_transport.urlopen", fake)
    monkeypatch.setenv("OPENAI_API_KEY", "secret-that-must-not-be-persisted")
    client = OpenAIHTTPStandardClient(provider_account_project="proj_test")
    client.create_response_once(b'{"model":"gpt-5.6-luna"}', client_request_id="client-test")
    assert next(value for key, value in captured.items() if key.lower() == "openai-project") == "proj_test"
    assert "secret-that-must-not-be-persisted" not in captured.values()


def test_unbound_project_fails_before_urlopen(monkeypatch):
    monkeypatch.setenv("OPENAI_API_KEY", "secret")
    monkeypatch.setattr("charitygraph.phase5_standard_transport.urlopen", lambda *_a, **_k: pytest.fail("network seam reached"))
    with pytest.raises(StandardSystemic, match="project"):
        OpenAIHTTPStandardClient().create_response_once(b"{}", client_request_id="client-test")
