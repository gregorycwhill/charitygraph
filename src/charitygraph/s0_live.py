"""Canonical provider-free-testable live object construction seams."""
from __future__ import annotations

import hashlib
import json
from typing import Any, Callable

from .phase5_standard_transport import OpenAIHTTPStandardClient, OpenAIResponsesWebSearchTransport
from .s0_locator_discovery import OpenAIResponsesWebSearchProvider, S0LocatorSearchExecutionGate
from .scale_s0 import ScalePreflightError


def _identity(value: str) -> str:
    return hashlib.sha256(json.dumps({"locator_search": value}, sort_keys=True, separators=(",", ":")).encode()).hexdigest()


def canonical_locator_provider_factory(*, client: OpenAIHTTPStandardClient) -> Callable[[Any, Any, Any], OpenAIResponsesWebSearchProvider]:
    """Return a per-item factory; only stateless HTTP configuration is reused."""
    if not isinstance(client, OpenAIHTTPStandardClient) or not client.provider_account_project:
        raise ScalePreflightError("live locator factory requires a project-bound canonical HTTP client")

    def create(request: Any, packet: Any, preflight: Any) -> OpenAIResponsesWebSearchProvider:
        if request.provider_account_project != client.provider_account_project:
            raise ScalePreflightError("HTTP client project does not match the request A3 project")
        identity = packet.provider_request_identity
        gate = S0LocatorSearchExecutionGate(
            preflight=preflight, request=request, catalog=preflight.catalog,
            delivery_attempt_id="delivery-attempt:" + _identity(identity),
            client_request_id="locator-search-client:" + _identity(identity),
            request_identity=identity,
        )
        return OpenAIResponsesWebSearchProvider(OpenAIResponsesWebSearchTransport(client), model="gpt-5.6-luna", execution_gate=gate)

    return create
