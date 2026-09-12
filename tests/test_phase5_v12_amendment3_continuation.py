from __future__ import annotations

import ast
import importlib.util
from pathlib import Path

import pytest

_path = Path("scripts/continue_phase5_direct_service_v12_amendment3.py")
_spec = importlib.util.spec_from_file_location("v12_amendment3_continuation", _path)
_module = importlib.util.module_from_spec(_spec)
assert _spec and _spec.loader
_spec.loader.exec_module(_module)
FAILED_CANARY = _module.FAILED_CANARY
select_surviving_rows = _module.select_surviving_rows


def test_continuation_excludes_only_failed_canary_and_preserves_manifest_order():
    ids = [f"requestitem:{n:064x}" for n in range(18)]
    ids[7] = FAILED_CANARY
    rows = [{"provider_request_item_id": item, "ordinal": index} for index, item in enumerate(ids)]
    selected = select_surviving_rows(rows)
    assert len(selected) == 17
    assert all(row["provider_request_item_id"] != FAILED_CANARY for row in selected)
    assert [row["ordinal"] for row in selected] == [i for i in range(18) if i != 7]


@pytest.mark.parametrize("ids", [[], [{"provider_request_item_id": "duplicate"}] * 18])
def test_continuation_rejects_non_exact_manifest_shape(ids):
    with pytest.raises(RuntimeError, match="exact 18-item"):
        select_surviving_rows(ids)


def test_continuation_entry_point_does_not_activate_or_reprepare_authority():
    path = Path("scripts/continue_phase5_direct_service_v12_amendment3.py")
    tree = ast.parse(path.read_text(encoding="utf-8"))
    called = {
        node.func.attr
        for node in ast.walk(tree)
        if isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute)
    }
    forbidden = {
        "activate_execution_mandate",
        "revoke_execution_mandate",
        "register_execution_mandate",
        "reserve_execution_mandate",
        "reserve_cost",
        "prepare_physical_attempt",
        "create_provider_request_item",
        "create_provider_request_attempt",
        "create_zero_crossing_pre_send_replacement",
    }
    assert not called.intersection(forbidden)
