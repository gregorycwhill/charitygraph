"""Reproduce the review-only fundraising profile artifact from its fixture."""
from __future__ import annotations

import json
from pathlib import Path

from charitygraph.fundraising_review_projection import FundraisingReviewArtifact, render_markdown

ROOT = Path(__file__).resolve().parents[1]
FIXTURE = ROOT / "tests" / "fixtures" / "fundraising_review_profile.json"
OUTPUT = ROOT / "artifacts" / "fundraising-review"


def main() -> None:
    artifact = FundraisingReviewArtifact.model_validate_json(FIXTURE.read_text(encoding="utf-8"))
    OUTPUT.mkdir(parents=True, exist_ok=True)
    (OUTPUT / "fundraising-review-profile.json").write_text(artifact.canonical_json() + "\n", encoding="utf-8")
    (OUTPUT / "fundraising-review-profile.md").write_text(render_markdown(artifact), encoding="utf-8")
    (OUTPUT / "manifest.json").write_text(json.dumps({"contract_version": artifact.contract_version, "input_sha256": artifact.sha256, "fixture": "tests/fixtures/fundraising_review_profile.json"}, sort_keys=True, indent=2) + "\n", encoding="utf-8")


if __name__ == "__main__":
    main()
