from __future__ import annotations

import csv
import json
from pathlib import Path

import pytest

from charitygraph.identity_bootstrap import _archive_rows, identity_map_hash


def test_archive_identity_rows_require_exact_abn_and_name(tmp_path: Path) -> None:
    path = tmp_path / "register.csv"
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=["ABN", "Charity_Legal_Name"])
        writer.writeheader()
        writer.writerow({"ABN": "12345678901", "Charity_Legal_Name": "Exact Charity"})
    assert _archive_rows(path, [{"abn": "12345678901"}]) == {"12345678901": {"name": "Exact Charity"}}


def test_archive_identity_rows_reject_missing_exact_match(tmp_path: Path) -> None:
    path = tmp_path / "register.csv"
    path.write_text("ABN,Charity_Legal_Name\n12345678901,\n", encoding="utf-8")
    with pytest.raises(RuntimeError, match="no registered name"):
        _archive_rows(path, [{"abn": "12345678901"}])


def test_identity_map_hash_is_order_independent_and_subject_ids_are_opaque() -> None:
    rows = [
        {"rank": 2, "abn": "22345678901", "subject_id": "subject:bbbb", "status": "created_from_reused_acnc_source"},
        {"rank": 1, "abn": "12345678901", "subject_id": "subject:aaaa", "status": "reused_existing_subject"},
    ]
    assert identity_map_hash(rows) == identity_map_hash(list(reversed(rows)))
    assert all(row["subject_id"] != f"subject:{row['abn']}" for row in rows)


def test_bootstrap_module_has_no_semantic_task_or_provider_entrypoint() -> None:
    text = Path("src/charitygraph/identity_bootstrap.py").read_text(encoding="utf-8")
    assert "responses.create" not in text
    assert "model_task" not in text
    assert "provider_calls" not in text
