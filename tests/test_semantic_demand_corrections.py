import pytest

from charitygraph.contracts.semantic_demand_corrections import (
    CorrectionLocus, GovernedObservation, evaluate_governed_replacement,
)


def observation():
    return GovernedObservation("obs-1", "old governed value", "2025-01-01")


def test_full_supersession_preserves_historical_knowledge_and_changes_current():
    historical, current = evaluate_governed_replacement(
        prior=observation(), decision="accept_governed_replacement",
        replacement_value="amended governed value", locus=CorrectionLocus.CANONICAL_OBSERVATION,
        challenge_basis="amended authoritative report")
    assert historical.value == "old governed value" and historical.valid_to == "decision-time"
    assert current and current.value == "amended governed value" and current.supersedes == "obs-1"


@pytest.mark.parametrize("locus,value", [
    (CorrectionLocus.REPRESENTATION, "re-extracted value"),
    (CorrectionLocus.IDENTITY_BINDING, "correct subject binding"),
    (CorrectionLocus.SCOPE_BINDING, "qualified scope"),
    (CorrectionLocus.SEMANTIC_MAPPING, "designation only"),
])
def test_governed_repair_classes_append_successor(locus, value):
    _, successor = evaluate_governed_replacement(prior=observation(), decision="accept_qualification", replacement_value=value, locus=locus, challenge_basis="replayable evidence")
    assert successor and successor.supersedes == "obs-1"


@pytest.mark.parametrize("decision,basis", [("reject_insufficient", "assertion only"), ("reject_unsupported", "" )])
def test_rejected_or_insufficient_challenge_cannot_change_governed_state(decision, basis):
    prior, successor = evaluate_governed_replacement(prior=observation(), decision=decision, replacement_value="attempted overwrite", locus=CorrectionLocus.CANONICAL_OBSERVATION, challenge_basis=basis, affiliation="subject organisation")
    assert prior == observation() and successor is None


def test_projection_only_fix_cannot_silently_overwrite_governed_observation():
    prior, successor = evaluate_governed_replacement(prior=observation(), decision="accept_governed_replacement", replacement_value="patched output", locus=CorrectionLocus.PROJECTION, challenge_basis="renderer comparison")
    assert prior == observation() and successor is None


def test_unsupported_accepted_change_fails_closed():
    with pytest.raises(ValueError, match="replacement"):
        evaluate_governed_replacement(prior=observation(), decision="accept_governed_replacement", replacement_value=None, locus=CorrectionLocus.CANONICAL_OBSERVATION, challenge_basis="unsupported assertion")
