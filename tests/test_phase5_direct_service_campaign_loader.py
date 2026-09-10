import pytest

from scripts.run_phase5_direct_service_standard_campaign import canonicalize_prepared_campaign_rows, response_output_text


def _row(**overrides):
    row = {
        "provider_request_item_id": "requestitem:" + "a" * 64,
        "semantic_contract_hash": "b" * 64,
        "request_body": {"metadata": {"semantic_contract_hash": "b" * 64}},
    }
    row.update(overrides)
    return row


def test_historical_semantic_contract_hash_normalizes_to_canonical_identity():
    result = canonicalize_prepared_campaign_rows({"request_items": [{}]}, [_row()])
    assert result[0]["contract_identity_hash"] == "b" * 64
    assert result[0]["wire_fingerprint"] == "a" * 64
    assert "semantic_contract_hash" not in result[0]


def test_canonical_and_historical_contract_aliases_must_agree():
    with pytest.raises(RuntimeError, match="conflicting aliases"):
        canonicalize_prepared_campaign_rows(
            {"request_items": [{}]},
            [_row(contract_identity_hash="c" * 64)],
        )


def test_missing_contract_identity_alias_fails_closed():
    with pytest.raises(RuntimeError, match="missing canonical field"):
        canonicalize_prepared_campaign_rows(
            {"request_items": [{}]},
            [_row(semantic_contract_hash=None)],
        )


def test_responses_output_text_is_extracted_from_standard_output_content():
    assert response_output_text({"output": [{"type": "message", "content": [{"type": "output_text", "text": "{"}, {"type": "output_text", "text": "}"}]}]}) == "{}"


def test_responses_output_text_fails_closed_when_missing():
    with pytest.raises(ValueError, match="no output text"):
        response_output_text({"output": []})
