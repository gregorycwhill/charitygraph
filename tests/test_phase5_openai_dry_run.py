import json
from decimal import Decimal

import pytest

from charitygraph.phase5_openai_dry_run import RealProviderExecutionGate, parse_provider_result, serialize_fallback


def test_real_provider_gate_denies_by_default() -> None:
    with pytest.raises(PermissionError):
        RealProviderExecutionGate().assert_allowed(run_id="run:x", plan_hash="hash", exposure_usd=Decimal("1"))


def test_provider_result_unknown_custom_id_fails_closed() -> None:
    with pytest.raises(ValueError):
        parse_provider_result({"custom_id": "requestitem:unknown"}, {"requestitem:known"})


def test_flex_fallback_uses_responses_service_tier() -> None:
    request = type("Request", (), {"provider_request_item_id": "requestitem:one", "body": {"model": "gpt-5.6-luna"}})()
    assert serialize_fallback(request, "flex")["body"]["service_tier"] == "flex"
