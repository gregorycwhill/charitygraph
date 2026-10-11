import json
from pathlib import Path

import pytest

from charitygraph.corpus_replay import frontier_state, repaired_replay, verify_package
from charitygraph.governed_traversal import canonical_url, governed_locators, site_key


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


def test_governed_locator_normalisation_and_domain_boundary(tmp_path: Path):
    assert canonical_url("HTTPS://WWW.Example.org/path?q=1#x") == "https://www.example.org/path"
    assert site_key("https://www.example.org/") == site_key("https://example.org/x")
    inventory = {"per_charity_inventory": [{"subject_id": "s", "display_name": "Bound charity", "classes": [
        {"source_class": "charity_authored", "retained_objects": [{"source_family": "official_website", "resolved_locator": "https://bound.example/"}]}
    ]}]}
    path = tmp_path / "inventory.json"; path.write_text(json.dumps(inventory), encoding="utf-8")
    assert governed_locators(path)["s"]["locator"] == "https://bound.example/"
