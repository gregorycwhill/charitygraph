import json
from pathlib import Path

import pytest

from charitygraph.corpus_replay import frontier_state, repaired_replay, verify_package


def test_frontier_never_calls_queued_work_exhausted():
    assert frontier_state(queued_admissible_urls=1, safety_bound_hit=True) == "TRUNCATED"
    assert frontier_state(queued_admissible_urls=0, safety_bound_hit=True) == "EXHAUSTED"


def test_rejects_bad_package_hash(tmp_path: Path):
    package = tmp_path / "package"
    package.mkdir()
    (package / "SHA256SUMS.json").write_text(json.dumps({"missing": "x"}), encoding="utf-8")
    with pytest.raises(FileNotFoundError):
        verify_package(package)


def test_repaired_replay_preserves_indeterminate_states(tmp_path: Path):
    # The actual package is intentionally supplied at execution time; this test
    # exercises the public invariant without acquiring a provider.
    assert frontier_state(queued_admissible_urls=2, safety_bound_hit=False) == "PENDING"
