from pathlib import Path
import os
import shutil

import pytest

from charitygraph.s0_authorisation import ScalePreflightError, load_authorisation_package, plan_task_instances, validate_authorisation_package


DATA_PACKAGE = Path(os.environ.get("CHARITYGRAPH_S0_DATA_PACKAGE", Path(__file__).resolve().parents[2] / ".s0-policy-data"))


def copy_package(source: Path, target: Path) -> None:
    for item in source.rglob("*"):
        if item.is_file() and ".git" not in item.parts:
            destination = target / item.relative_to(source)
            destination.parent.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(item, destination)


def test_authorised_production_package_validates_without_synthetic_approval() -> None:
    mandate = validate_authorisation_package(DATA_PACKAGE)
    assert mandate.authorizing_actor_ref == "SCALE_S0_AUTHORISATION_DECISION_2026-09-18.md#S0_AUTHORISED"


def test_production_loader_selects_authorised_mandate() -> None:
    mandate, *_ = load_authorisation_package(DATA_PACKAGE)
    assert mandate.authorizing_actor_ref.endswith("#S0_AUTHORISED")


def test_shadow_requires_explicit_test_only_path() -> None:
    with pytest.raises(ScalePreflightError, match="missing|required|synthetic test approval"):
        validate_authorisation_package(DATA_PACKAGE, authority="shadow")


def test_missing_or_invalid_authorised_mandate_never_falls_back_to_shadow(tmp_path: Path) -> None:
    copy_package(DATA_PACKAGE, tmp_path)
    (tmp_path / "SCALE_S0_MANDATE_AUTHORISED_V2.yaml").unlink()
    with pytest.raises(ScalePreflightError, match="authorised mandate|decision record|package artifact"):
        load_authorisation_package(tmp_path)
    copy_package(DATA_PACKAGE, tmp_path)
    authorised = tmp_path / "SCALE_S0_MANDATE_AUTHORISED_V2.yaml"
    authorised.write_text(authorised.read_text(encoding="utf-8").replace("S0_AUTHORISED", "S0_NOT_AUTHORISED"), encoding="utf-8")
    with pytest.raises(ScalePreflightError, match="authorisation reference|hash|mandate"):
        load_authorisation_package(tmp_path)


def test_unapproved_candidate_fails_closed() -> None:
    with pytest.raises(ScalePreflightError, match="missing required frozen"):
        validate_authorisation_package(DATA_PACKAGE, authority="shadow")


def test_synthetic_approval_validates_complete_immutable_package() -> None:
    mandate = validate_authorisation_package(DATA_PACKAGE, authority="shadow", synthetic_approval=True)
    assert mandate.authorizing_actor_ref == "TEST_ONLY_SYNTHETIC_APPROVAL"
    assert mandate.per_request_reservation_cap == "0.25"


def test_policy_hash_substitution_is_rejected(tmp_path: Path) -> None:
    # Loader validates the immutable package directly; a substituted manifest hash cannot bind it.
    copy_package(DATA_PACKAGE, tmp_path)
    source = tmp_path / "SCALE_S0_POLICY_BUNDLE_BALANCED_V1.yaml"
    source.write_text(source.read_text(encoding="utf-8").replace("AC188F09", "BC188F09", 1), encoding="utf-8")
    with pytest.raises(ScalePreflightError, match="hash"):
        load_authorisation_package(tmp_path)


def test_offline_task_planner_enumerates_the_full_registry_cartesian_product() -> None:
    instances = plan_task_instances(DATA_PACKAGE)
    assert len(instances) == 168
    assert sum(item["kind"] == "deterministic" for item in instances) == 24
    assert sum(item["kind"] == "semantic" for item in instances) == 136
    assert sum(item["kind"] == "human_only" for item in instances) == 8
    assert {item["applicability"] for item in instances} == {"CONDITIONAL_PENDING_SOURCE"}
