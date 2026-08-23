from datetime import datetime, timedelta, timezone
from decimal import Decimal
from pathlib import Path
import os
import subprocess
import sys

import pytest

from charitygraph.contracts.canonical import canonical_data, canonical_json_bytes, canonical_sha256, seal_record, verify_record_hash
from ._helpers import subject


def test_known_answer_order_independence_and_schema_wire_alias():
    value = {"b": "e\u0301", "a": Decimal("1.2300")}
    assert canonical_data(value) == {"a": "1.23", "b": "é"}
    assert canonical_json_bytes(value) == '{"a":"1.23","b":"é"}'.encode()
    assert canonical_sha256(value) == "7016f49f7753d93a61a9afa1040cdfd816d5c3118676bd65f44d8707af5aab81"
    assert canonical_sha256({"a": 1, "b": 2}) == canonical_sha256({"b": 2, "a": 1})
    assert canonical_sha256([1, 2]) != canonical_sha256([2, 1])
    serialized = subject().model_dump(by_alias=True)
    assert "schema" in serialized and "schema_ref" not in serialized
    assert canonical_sha256(subject()) == canonical_sha256(subject().model_dump(by_alias=True))


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


def test_aware_datetimes_are_equivalent_in_utc_but_distinct_instants_are_not():
    left = datetime(2026, 1, 1, 0, 0, tzinfo=timezone.utc)
    same_in_sydney = datetime(2026, 1, 1, 11, 0, tzinfo=timezone(timedelta(hours=11)))
    later = datetime(2026, 1, 1, 0, 1, tzinfo=timezone.utc)
    assert canonical_sha256(left) == canonical_sha256(same_in_sydney)
    assert canonical_sha256(left) != canonical_sha256(later)


def test_contract_import_has_no_schema_shadow_warnings():
    root = Path(__file__).resolve().parents[2]
    environment = {**os.environ, "PYTHONPATH": str(root / "src")}
    result = subprocess.run(
        [sys.executable, "-W", "error", "-c", "import charitygraph.contracts"],
        capture_output=True, text=True, env=environment,
    )
    assert result.returncode == 0, result.stderr
