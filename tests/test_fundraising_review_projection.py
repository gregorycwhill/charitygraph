import json
from pathlib import Path

from charitygraph.fundraising_review_projection import FundraisingReviewArtifact, render_markdown


FIXTURE = Path(__file__).parent / "fixtures" / "fundraising_review_profile.json"


def test_review_fixture_is_deterministic_and_exposes_required_consumer_distinctions():
    artifact = FundraisingReviewArtifact.model_validate_json(FIXTURE.read_text(encoding="utf-8"))
    first, second = artifact.canonical_json(), artifact.canonical_json()
    rendered = render_markdown(artifact)
    assert first == second
    assert len(artifact.subjects) == 4
    assert "organisation (not attributed)" in rendered
    assert "not_found_in_scoped_source" in rendered
    assert "lifecycle `current`" in rendered
    assert "Winter Community Appeal" in rendered
    assert "cb_review_platform" in rendered
    assert "125000 AUD" in rendered
    assert artifact.sha256


def test_review_artifact_has_no_unsupported_fundraising_performance_claim():
    artifact = FundraisingReviewArtifact.model_validate_json(FIXTURE.read_text(encoding="utf-8"))
    rendered = render_markdown(artifact).lower()
    forbidden = ("roi", "cost-to-raise", "donor acquisition cost", "lifetime value", "profitability", "causal uplift")
    assert not any(term in rendered for term in forbidden)
    assert all(link.linkage_status == "unknown" for link in artifact.subjects[2].money)


def test_fixture_is_review_only_and_not_presented_as_production_source_acquisition():
    payload = json.loads(FIXTURE.read_text(encoding="utf-8"))
    assert payload["capability_scope"] == "review_only_representative_slice"
    assert all(subject["evidence_set_id"].startswith("cached-governed-review-case-") for subject in payload["subjects"])
