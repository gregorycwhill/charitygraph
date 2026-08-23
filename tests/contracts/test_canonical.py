from datetime import datetime, timezone
from decimal import Decimal
from pathlib import Path

import pytest

from charitygraph.contracts.canonical import canonical_data, canonical_json_bytes, canonical_sha256, seal_record, verify_record_hash
from ._helpers import subject


def test_known_answer_and_order_independence():
    value = {"b": "e\u0301", "a": Decimal("1.2300")}
    assert canonical_data(value) == {"a": "1.23", "b": "é"}
    assert canonical_json_bytes(value) == '{"a":"1.23","b":"é"}'.encode()
    assert canonical_sha256(value) == "7016f49f7753d93a61a9afa1040cdfd816d5c3118676bd65f44d8707af5aab81"
    assert canonical_sha256({"a": 1, "b": 2}) == canonical_sha256({"b": 2, "a": 1})
    assert canonical_sha256([1, 2]) != canonical_sha256([2, 1])


@pytest.mark.parametrize("value", [1.2, {1, 2}, Path("x"), datetime(2026, 1, 1)])
def test_rejects_noncanonical_values(value):
    with pytest.raises((TypeError, ValueError)):
        canonical_data(value)


def test_seal_verify_and_tamper_detection():
    record = subject()
    sealed = seal_record(record)
    assert sealed.content_hash is not None
    assert verify_record_hash(sealed)
    tampered = sealed.model_copy(update={"display_name": "Tampered"})
    assert not verify_record_hash(tampered)
    with pytest.raises(ValueError):
        seal_record(tampered)


def test_aware_datetimes_are_equivalent_in_utc():
    left = datetime(2026, 1, 1, tzinfo=timezone.utc)
    right = datetime(2026, 1, 1, 11, tzinfo=timezone.utc).replace(hour=0)
    assert canonical_sha256(left) == canonical_sha256(right)
