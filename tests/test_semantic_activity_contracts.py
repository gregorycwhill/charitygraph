import pytest
from pydantic import ValidationError

from charitygraph.contracts.semantic import (
    SEMANTIC_OUTPUT_MODELS,
    OperationalActivityAssignmentOutput,
    OperationalActivitySelection,
    SDGAlignmentOutput,
    SemanticConclusion,
    SemanticEvidence,
    TaxonomySelection,
)
from charitygraph.contracts.ids import deterministic_id


def _evidence() -> tuple[SemanticEvidence, ...]:
    return (SemanticEvidence(evidence_id="evidence:captured-1", role="supporting", note="bounded source span"),)


def _conclusion() -> SemanticConclusion:
    return SemanticConclusion(outcome="supported", evidence=_evidence(), rationale="Evidence supports the bounded proposal.")


@pytest.mark.parametrize("activity_id", ("activity.advocacy", "activity.policy_change"))
def test_native_operational_activity_proposals_validate_with_evidence(activity_id: str) -> None:
    output = OperationalActivityAssignmentOutput(
        conclusion=_conclusion(),
        selections=(OperationalActivitySelection(activity_id=activity_id, evidence=_evidence(), rationale="Bounded activity interpretation."),),
    )
    assert output.selections[0].activity_id == activity_id


def test_activity_assignment_cannot_use_external_scheme_or_duplicate_ids() -> None:
    with pytest.raises(ValidationError, match="activity.\\* IDs"):
        OperationalActivitySelection(activity_id="concept:external", evidence=_evidence(), rationale="Wrong namespace.")
    selection = OperationalActivitySelection(activity_id="activity.advocacy", evidence=_evidence(), rationale="Bounded activity interpretation.")
    with pytest.raises(ValidationError, match="unique"):
        OperationalActivityAssignmentOutput(conclusion=_conclusion(), selections=(selection, selection))


@pytest.mark.parametrize("goal_number", (13, 15))
def test_sdg_remains_a_separate_evidence_bound_scheme_alignment(goal_number: int) -> None:
    goal_id = deterministic_id("concept:", {"scheme_id": "un-sdg", "authority_goal_number": goal_number})
    output = SDGAlignmentOutput(
        conclusion=_conclusion(),
        sdg_selections=(TaxonomySelection(concept_id=goal_id, role="secondary", evidence=_evidence(), rationale="Evidence-bound alignment proposal."),),
    )
    assert output.sdg_selections[0].concept_id == goal_id


def test_activity_and_sdg_never_cross_namespaces() -> None:
    with pytest.raises(ValidationError, match="concept: IDs"):
        TaxonomySelection(concept_id="activity.advocacy", role="primary", evidence=_evidence(), rationale="Wrong namespace.")


def test_task_registry_routes_activities_to_the_native_activity_contract() -> None:
    assert SEMANTIC_OUTPUT_MODELS["operational_activity_assignment"] is OperationalActivityAssignmentOutput
    assert SEMANTIC_OUTPUT_MODELS["sdg_alignment"] is SDGAlignmentOutput
