import json
from pathlib import Path

import pytest

from charitygraph.fundraising_evidence_roles import FundraisingEvidence, assess_fundraising_evidence


CASES = json.loads(Path("tests/fixtures/fundraising_evidence_role_cases.json").read_text())


@pytest.mark.parametrize("case", CASES, ids=lambda item: item["name"])
def test_role_fixture_decisions(case):
    payload = {key: value for key, value in case.items() if key not in {"name", "expected"}}
    assert assess_fundraising_evidence(FundraisingEvidence.model_validate(payload)).promotion == case["expected"]


@pytest.mark.parametrize("role", ["pfra_membership", "regulator_registration"])
def test_pfra_and_regulator_non_inference_gates_are_mechanical(role):
    payload = dict(CASES[2] if role == "pfra_membership" else CASES[3])
    payload.pop("name"); payload.pop("expected")
    payload["source_role"] = role
    payload["asserted_facets"] = ["practice"]
    with pytest.raises(ValueError, match="cannot support facets"):
        FundraisingEvidence.model_validate(payload)


def test_currentness_requires_explicit_valid_time():
    payload = dict(CASES[0]); payload.pop("name"); payload.pop("expected")
    payload.pop("valid_from")
    with pytest.raises(ValueError, match="currentness requires"):
        FundraisingEvidence.model_validate(payload)


def test_scoped_silence_cannot_become_a_negative_practice():
    payload = dict(CASES[-1]); payload.pop("name"); payload.pop("expected")
    payload["asserted_facets"] = ["practice"]
    with pytest.raises(ValueError, match="scoped source silence"):
        FundraisingEvidence.model_validate(payload)
