from datetime import datetime, timezone
from decimal import Decimal
import json

import pytest

from charitygraph.contracts.economics import PriceRate, PricingSnapshot
from charitygraph.contracts.common import ProducerRef
from charitygraph.s0_pricing import derive_luna_web_search_cost
from charitygraph.scale_s0 import ScalePreflightError


NOW = datetime(2026, 9, 25, tzinfo=timezone.utc)


def snapshot():
    return PricingSnapshot(
        record_id="pricing:" + "b" * 64, provider_id="openai", model_snapshot="gpt-5.6-luna",
        effective_at=NOW, retrieved_at=NOW, provider_currency="USD",
        authoritative_source_url="https://developers.openai.com/api/docs/pricing",
        source_content_hash="a" * 64,
        created_at=NOW, producer=ProducerRef(kind="automation_policy", producer_id="terra"),
        rates=(PriceRate(dimension="input_tokens", unit_quantity=1000000, price_per_unit="0.20"),
               PriceRate(dimension="cached_input_tokens", unit_quantity=1000000, price_per_unit="0.02"),
               PriceRate(dimension="output_tokens", unit_quantity=1000000, price_per_unit="1.20"),
               PriceRate(dimension="tool_calls", unit_quantity=1000, price_per_unit="10.00")),
    )


def body(*, input_tokens=100, cached=20, output_tokens=50, calls=1, model="gpt-5.6-luna"):
    output = [{"type": "web_search_call", "action": {"type": "search"}} for _ in range(calls)]
    output.append({"type": "message", "content": []})
    return {"id": "resp_1", "model": model, "usage": {"input_tokens": input_tokens, "output_tokens": output_tokens, "input_tokens_details": {"cached_tokens": cached}}, "output": output}


def test_derives_uncached_cached_output_and_tool_cost_without_provider_dollar_fields():
    evidence = derive_luna_web_search_cost(snapshot=snapshot(), response_body=body())
    expected = Decimal("80") / Decimal(1_000_000) * Decimal("0.20") + Decimal("20") / Decimal(1_000_000) * Decimal("0.02") + Decimal("50") / Decimal(1_000_000) * Decimal("1.20") + Decimal("10") / Decimal(1000)
    assert evidence.amount_usd == expected
    assert "provider_cost" not in evidence.usage


def test_long_context_and_multiple_calls_are_priced_deterministically():
    evidence = derive_luna_web_search_cost(snapshot=snapshot(), response_body=body(input_tokens=272001, cached=1, output_tokens=2, calls=2))
    assert evidence.web_search_calls == 2
    assert evidence.amount_usd > Decimal("0.02")


@pytest.mark.parametrize("bad", [
    {"input_tokens": -1, "output_tokens": 1},
    {"input_tokens": 1, "output_tokens": 1, "input_tokens_details": {"cached_tokens": 2}},
    {"input_tokens": 1, "output_tokens": 1, "input_tokens_details": {"cached_tokens": "1"}},
])
def test_malformed_usage_fails_closed(bad):
    value = body()
    value["usage"].update(bad)
    with pytest.raises(ScalePreflightError):
        derive_luna_web_search_cost(snapshot=snapshot(), response_body=value)


def test_model_mismatch_and_malformed_search_action_fail_closed():
    with pytest.raises(ScalePreflightError):
        derive_luna_web_search_cost(snapshot=snapshot(), response_body=body(model="gpt-5.6-terra"))
    value = body(); value["output"][0]["action"] = {}
    with pytest.raises(ScalePreflightError):
        derive_luna_web_search_cost(snapshot=snapshot(), response_body=value)
