import pytest
from pydantic import ValidationError

from charitygraph.contracts import AutomationAuthority, CandidateObservation, DerivativeArtifact, validate_promotion_chain
from ._helpers import Payload, candidate, decision, observation, ref, subject


def test_subject_and_candidate_contracts_are_strict_and_immutable():
    value = subject()
    with pytest.raises((ValidationError, TypeError)):
        type(value)(**{**value.model_dump(), "unexpected": True})
    with pytest.raises(ValidationError):
        CandidateObservation[Payload](**{**candidate().model_dump(), "unknown": True})
    with pytest.raises(ValidationError):
        candidate().payload.value = "changed"


def test_candidate_fingerprint_changes_with_payload_not_creation_metadata():
    first = candidate()
    changed = CandidateObservation[Payload](
        **{**first.model_dump(), "record_id": "candidate:" + "8" * 32, "payload": Payload(value="different"), "candidate_fingerprint": None}
    )
    assert first.candidate_fingerprint != changed.candidate_fingerprint


def test_identity_and_lifecycle_invariants():
    with pytest.raises(ValidationError):
        CandidateObservation[Payload](**{**candidate().model_dump(), "identity_state": "unresolved", "subject_id": None})
    with pytest.raises(ValidationError):
        type(subject())(**{**subject().model_dump(), "lifecycle_status": "tombstoned"})


def test_decision_authority_and_promotion_chain():
    cand = candidate()
    dec = decision(cand)
    obs = observation(cand, dec)
    validate_promotion_chain(cand, dec, obs)
    with pytest.raises(ValidationError):
        type(dec)(**{**dec.model_dump(), "producer": {"kind": "model", "producer_id": "model", "version": "1"}})
    with pytest.raises(ValidationError):
        AutomationAuthority(policy_id="p", policy_version="1", benchmark_artifact_ids=())


def test_promotion_requires_review_and_promotion_edges():
    cand = candidate()
    dec = decision(cand)
    obs = observation(cand, dec).model_copy(update={"lineage": ()})
    with pytest.raises(ValueError):
        validate_promotion_chain(cand, dec, obs)


def test_derivative_requires_canonical_input_and_invalidation():
    cand = candidate()
    dec = decision(cand)
    obs = observation(cand, dec)
    derivative = DerivativeArtifact[Payload](
        record_id="derivative:" + "9" * 32, created_at=obs.created_at,
        producer={"kind":"code","producer_id":"summary","version":"1"}, derivative_type="summary",
        payload_schema=obs.payload_schema, payload=Payload(value="summary"), input_observation_ids=(obs.record_id,),
        generation_policy_id="summary-v1", release_safe=True,
    )
    assert derivative.input_observation_ids == (obs.record_id,)
    with pytest.raises(ValidationError):
        DerivativeArtifact[Payload](**{**derivative.model_dump(), "status": "invalidated", "invalidated_by_ids": ()})
