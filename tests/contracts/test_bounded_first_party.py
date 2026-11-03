import hashlib
import json

import pytest

from charitygraph.bounded_first_party import CATEGORIES, CoverageError, freeze_completeness


def _sha(data): return hashlib.sha256(data).hexdigest()


def _inputs(tmp_path):
    raw = b"retained source"; raw_hash = _sha(raw)
    rep = b'{"representation":"retained"}'; rep_hash = _sha(rep)
    (tmp_path / "raw").mkdir(); (tmp_path / "representations").mkdir()
    (tmp_path / "raw" / raw_hash).write_bytes(raw)
    (tmp_path / "representations" / f"{rep_hash}.json").write_bytes(rep)
    cohort = {"freeze": {"cohort_sha256": _sha(b"cohort")}, "per_charity_inventory": [{"case_id": "C1"}]}
    attempt = {"attempt_id": "a1", "case_id": "C1", "source_class": "charity_authored", "status": "captured", "raw_sha256": raw_hash, "representation_sha256": rep_hash}
    coverage = [{"case_id": "C1", "category": category, "terminal_state": "UNAVAILABLE", "attempt_ids": ["a1"]} for category in CATEGORIES]
    return cohort, [attempt], coverage


def test_freeze_requires_every_category_and_replayable_capture(tmp_path):
    cohort, attempts, coverage = _inputs(tmp_path)
    result = freeze_completeness(cohort=cohort, attempts=attempts, coverage=coverage, archive_root=tmp_path)
    assert result["all_categories_terminal"] and result["provider_calls"] == 0
    with pytest.raises(CoverageError, match="exactly every"):
        freeze_completeness(cohort=cohort, attempts=attempts, coverage=coverage[:-1], archive_root=tmp_path)


def test_freeze_rejects_unauthorised_or_unreplayable_material(tmp_path):
    cohort, attempts, coverage = _inputs(tmp_path)
    attempts[0]["source_class"] = "general_media"
    with pytest.raises(CoverageError, match="unauthorised"):
        freeze_completeness(cohort=cohort, attempts=attempts, coverage=coverage, archive_root=tmp_path)
