import pytest

from charitygraph.north_star_projection import NorthStarLensOutput, project_with_compatibility_gate
from charitygraph.projection_compatibility import Disposition, EvaluationGrain, compose_audits, evaluate_compatibility

BASE = dict(answer_intent="describe", claim_family="service", authority_source_role="regulatory",
            currentness="current", scope="organisation", coverage="observed", evidence_refs=("e1",))

# Campaign-253 P6 regression shape: 30 deterministic golden/adversarial cases.
P6_CASES = [
    (f"P6-{i:02d}", {**BASE, "coverage": "not_available_from_source"}, Disposition.ALLOW_WITH_QUALIFICATION)
    for i in range(1, 11)
] + [
    (f"P6-{i:02d}", {**BASE, "currentness": "stale"}, Disposition.ABSTAIN)
    for i in range(11, 21)
] + [
    (f"P6-{i:02d}", {**BASE, "authority_source_role": "unknown"}, Disposition.ABSTAIN)
    for i in range(21, 31)
]

@pytest.mark.parametrize("case_id,inputs,expected", P6_CASES, ids=[c[0] for c in P6_CASES])
def test_p6_cases_are_monotonic_and_machine_readable(case_id, inputs, expected):
    audit = evaluate_compatibility(inputs, grain=EvaluationGrain.PROPOSITION)
    assert audit.disposition is expected
    assert audit.policy_version == "projection-compatibility.v1"
    assert audit.governed_inputs.evidence_refs == ("e1",)
    if expected is not Disposition.ALLOW:
        assert audit.required_qualifiers or audit.reason_codes
        assert audit.with_wording_review({"decision": "allow"}).disposition is expected

def test_missing_dimensions_abstain_with_explicit_reason_codes():
    audit = evaluate_compatibility({})
    assert audit.disposition is Disposition.ABSTAIN
    assert set(audit.reason_codes) >= {
        "MISSING_ANSWER_INTENT", "MISSING_CLAIM_FAMILY", "MISSING_AUTHORITY_SOURCE_ROLE",
        "MISSING_CURRENTNESS", "MISSING_SCOPE", "MISSING_COVERAGE",
    }

def test_composition_preserves_abstain_and_qualifiers():
    qualified = evaluate_compatibility({**BASE, "coverage": "unknown"}, grain=EvaluationGrain.CLAUSE)
    abstain = evaluate_compatibility({**BASE, "currentness": "stale"}, grain=EvaluationGrain.SECTION_CARD)
    result = compose_audits((qualified, abstain), grain=EvaluationGrain.WHOLE_ANSWER)
    assert result.disposition is Disposition.ABSTAIN
    assert {q.code for q in result.required_qualifiers} >= {"COVERAGE_LIMIT", "CURRENTNESS_LIMIT"}

def test_gate_is_at_projection_boundary():
    output = NorthStarLensOutput.model_validate({"assignments": [{"observation_key": "O001", "section_ids": [1]}]})
    projected, audit = project_with_compatibility_gate(output, BASE)
    assert projected is output and audit.disposition is Disposition.ALLOW
    projected, audit = project_with_compatibility_gate(output, {**BASE, "currentness": "stale"})
    assert projected is None and audit.disposition is Disposition.ABSTAIN
