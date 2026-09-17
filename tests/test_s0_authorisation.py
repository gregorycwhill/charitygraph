from pathlib import Path

import pytest

from charitygraph.s0_authorisation import ScalePreflightError, load_authorisation_package, validate_authorisation_package


DATA_PACKAGE = Path(__file__).resolve().parents[2] / ".s0-policy-data"


def test_unapproved_candidate_fails_closed() -> None:
    with pytest.raises(ScalePreflightError, match="missing required frozen"):
        validate_authorisation_package(DATA_PACKAGE)


def test_synthetic_approval_validates_complete_immutable_package() -> None:
    mandate = validate_authorisation_package(DATA_PACKAGE, synthetic_approval=True)
    assert mandate.authorizing_actor_ref == "TEST_ONLY_SYNTHETIC_APPROVAL"
    assert mandate.per_request_reservation_cap == "0.25"


def test_policy_hash_substitution_is_rejected(tmp_path: Path) -> None:
    # Loader validates the immutable package directly; a substituted manifest hash cannot bind it.
    source = DATA_PACKAGE / "SCALE_S0_POLICY_BUNDLE_BALANCED_V1.yaml"
    copied = tmp_path / "SCALE_S0_POLICY_BUNDLE_BALANCED_V1.yaml"
    copied.write_text(source.read_text(encoding="utf-8").replace("AC188F09", "BC188F09", 1), encoding="utf-8")
    for item in (DATA_PACKAGE / "policies").rglob("*.yaml"):
        target = tmp_path / item.relative_to(DATA_PACKAGE)
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(item.read_text(encoding="utf-8"), encoding="utf-8")
    (tmp_path / "SCALE_S0_SHADOW_MANDATE_V2.yaml").write_text((DATA_PACKAGE / "SCALE_S0_SHADOW_MANDATE_V2.yaml").read_text(encoding="utf-8"), encoding="utf-8")
    with pytest.raises(ScalePreflightError, match="hash"):
        load_authorisation_package(tmp_path)
