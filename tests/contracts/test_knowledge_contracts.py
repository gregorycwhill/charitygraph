import pytest
from pydantic import ValidationError

from charitygraph.contracts import AutomationAuthority, CandidateObservation, CanonicalObservation, DerivativeArtifact, LineageEdge, validate_promotion_chain
from ._helpers import NOW, Payload, SCHEMA, SUBJECT, candidate, decision, observation, ref, subject


def test_subject_and_candidate_contracts_are_strict_and_immutable():
    value = subject()
    with pytest.raises((ValidationError, TypeError)):
        type(value)(**{**value.model_dump(), "unexpected": True})
    with pytest.raises(ValidationError):
        CandidateObservation[Payload](**{**candidate().model_dump(), "unknown": True})
    with pytest.raises(ValidationError):
        candidate().payload.value = "changed"


def test_candidate_identity_states_are_explicit():
    with pytest.raises(ValidationError):
        candidate(subject_id=None, identity_state="resolved")
    assert candidate(subject_id=None, identity_state="unresolved").identity_state == "unresolved"
    with pytest.raises(ValidationError):
        candidate(subject_id=SUBJECT, identity_state="unresolved")
    assert candidate(subject_id=None, identity_state="ambiguous").identity_state == "ambiguous"
    with pytest.raises(ValidationError):
        candidate(subject_id=SUBJECT, identity_state="ambiguous")


def test_candidate_fingerprint_changes_with_payload_not_creation_metadata():
    first = candidate()
    changed = candidate(record_id="candidate:" + "8" * 32, payload=Payload(value="different"))
    assert first.candidate_fingerprint != changed.candidate_fingerprint


def test_subject_lifecycle_invariants():
    with pytest.raises(ValidationError):
        type(subject())(**{**subject().model_dump(), "lifecycle_status": "tombstoned"})


def test_accepted_promotion_reproduces_the_governed_proposition():
    cand = candidate(confidence="high", warnings=("qualified",))
    dec = decision(cand)
    obs = observation(cand, dec)
    validate_promotion_chain(cand, dec, obs)
    changed_payload = observation(cand, dec, payload=Payload(value="different"))
    with pytest.raises(ValueError, match="payload"):
        validate_promotion_chain(cand, dec, changed_payload)
    changed_evidence = observation(cand, dec, evidence_refs=(ref("evidence:" + "9" * 32),))
    with pytest.raises(ValueError, match="evidence"):
        validate_promotion_chain(cand, dec, changed_evidence)


def test_edited_promotion_requires_the_explicit_replacement_candidate():
    original = candidate()
    replacement = candidate(record_id="candidate:" + "8" * 32, payload=Payload(value="edited"))
    dec = decision(original, disposition="edited", replacement=replacement)
    obs = observation(replacement, dec)
    validate_promotion_chain(original, dec, obs, replacement)
    with pytest.raises(ValueError, match="require the supplied replacement"):
        validate_promotion_chain(original, dec, obs)
    with pytest.raises(ValueError, match="does not reference"):
        validate_promotion_chain(original, dec, observation(original, dec), replacement)
    different_subject = candidate(record_id="candidate:" + "9" * 32, subject_id="subject:" + "2" * 32, payload=Payload(value="edited"))
    different_decision = decision(original, disposition="edited", replacement=different_subject)
    with pytest.raises(ValueError, match="subject and scope"):
        validate_promotion_chain(original, different_decision, observation(different_subject, different_decision), different_subject)


def test_promotion_lineage_is_directed_and_exactly_corresponds_to_fields():
    cand = candidate()
    reversed_decision = decision(cand, lineage=(LineageEdge(edge_type="reviewed_by", source_artifact_id="decision:" + "6" * 32, target_artifact_id=cand.record_id),))
    with pytest.raises(ValueError, match="reviewed_by"):
        validate_promotion_chain(cand, reversed_decision, observation(cand, reversed_decision))
    dec = decision(cand)
    reversed_observation = observation(cand, dec, lineage=(LineageEdge(edge_type="promoted_as", source_artifact_id="observation:" + "7" * 32, target_artifact_id=cand.record_id),))
    with pytest.raises(ValueError, match="promoted_as"):
        validate_promotion_chain(cand, dec, reversed_observation)
    extra_review = decision(cand, lineage=(
        LineageEdge(edge_type="reviewed_by", source_artifact_id=cand.record_id, target_artifact_id="decision:" + "6" * 32),
        LineageEdge(edge_type="reviewed_by", source_artifact_id="candidate:" + "8" * 32, target_artifact_id="decision:" + "6" * 32),
    ))
    with pytest.raises(ValueError, match="exactly one reviewed_by"):
        validate_promotion_chain(cand, extra_review, observation(cand, extra_review))
    duplicate_promoted = observation(cand, dec, lineage=(
        LineageEdge(edge_type="promoted_as", source_artifact_id=cand.record_id, target_artifact_id="observation:" + "7" * 32),
        LineageEdge(edge_type="promoted_as", source_artifact_id=cand.record_id, target_artifact_id="observation:" + "7" * 32),
    ))
    with pytest.raises(ValueError, match="exactly one promoted_as"):
        validate_promotion_chain(cand, dec, duplicate_promoted)


def test_append_only_observation_and_derivative_lifecycle_contracts():
    cand = candidate()
    dec = decision(cand)
    prior_id = "observation:" + "8" * 32
    replacement = observation(cand, dec, supersedes_observation_id=prior_id, lineage=(
        LineageEdge(edge_type="promoted_as", source_artifact_id=cand.record_id, target_artifact_id="observation:" + "7" * 32),
        LineageEdge(edge_type="supersedes", source_artifact_id="observation:" + "7" * 32, target_artifact_id=prior_id),
    ))
    assert replacement.supersedes_observation_id == prior_id
    with pytest.raises(ValidationError, match="supersedes edges require"):
        observation(cand, dec, lineage=(
            LineageEdge(edge_type="promoted_as", source_artifact_id=cand.record_id, target_artifact_id="observation:" + "7" * 32),
            LineageEdge(edge_type="supersedes", source_artifact_id="observation:" + "7" * 32, target_artifact_id=prior_id),
        ))
    with pytest.raises(ValidationError, match="exactly one supersedes"):
        observation(cand, dec, supersedes_observation_id=prior_id, lineage=(
            LineageEdge(edge_type="promoted_as", source_artifact_id=cand.record_id, target_artifact_id="observation:" + "7" * 32),
            LineageEdge(edge_type="supersedes", source_artifact_id="observation:" + "7" * 32, target_artifact_id=prior_id),
            LineageEdge(edge_type="supersedes", source_artifact_id="observation:" + "7" * 32, target_artifact_id="observation:" + "9" * 32),
        ))
    with pytest.raises(ValidationError, match="supersedes edge must run"):
        observation(cand, dec, supersedes_observation_id=prior_id, lineage=(
            LineageEdge(edge_type="promoted_as", source_artifact_id=cand.record_id, target_artifact_id="observation:" + "7" * 32),
            LineageEdge(edge_type="supersedes", source_artifact_id=prior_id, target_artifact_id="observation:" + "7" * 32),
        ))
    with pytest.raises(ValidationError):
        CanonicalObservation[Payload](**{**observation(cand, dec).model_dump(), "status": "superseded"})
    derivative = DerivativeArtifact[Payload](
        record_id="derivative:" + "9" * 32, created_at=NOW,
        producer={"kind": "code", "producer_id": "summary", "version": "1"}, derivative_type="summary",
        payload_schema=SCHEMA, payload=Payload(value="summary"), input_observation_ids=(replacement.record_id,),
        generation_policy_id="summary-v1", release_safe=True,
    )
    assert derivative.release_safe is True
    with pytest.raises(ValidationError):
        DerivativeArtifact[Payload](**{**derivative.model_dump(), "status": "invalidated"})


def test_decision_authority_is_not_model_authority():
    cand = candidate()
    dec = decision(cand)
    with pytest.raises(ValidationError):
        type(dec)(**{**dec.model_dump(), "producer": {"kind": "model", "producer_id": "model", "version": "1"}})
    with pytest.raises(ValidationError):
        AutomationAuthority(policy_id="p", policy_version="1", benchmark_artifact_ids=())
