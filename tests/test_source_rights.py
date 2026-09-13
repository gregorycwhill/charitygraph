from datetime import date

import pytest

from charitygraph.source_rights import ArtifactRightsDecision, require_provider_rights


def decision(**changes):
    value = dict(decision_id="rights:1", source_artifact_id="srcblob:a", transmitted_representation_sha256="a" * 64,
        rights_policy_id="source-rights-v1", provider_processing_policy_id="openai-api-input-v1",
        rights_basis="explicit_open_license", evidence_locator="https://example.test/licence", evidence_sha256="b" * 64,
        assessed_on=date(2026, 9, 13), assessment_scope="private provider transmission", local_retention_allowed=True,
        provider_transmission_allowed=True, public_redistribution_allowed=False, attribution="Example")
    value.update(changes)
    return ArtifactRightsDecision.model_validate(value)


def test_public_access_is_not_a_provider_right():
    with pytest.raises(ValueError, match="cannot authorize"):
        decision(rights_basis="unknown")


def test_known_open_licence_can_authorize_private_processing_but_not_redistribution():
    value = decision()
    assert value.provider_transmission_allowed is True
    assert value.public_redistribution_allowed is False


@pytest.mark.parametrize("basis", ["unknown", "prohibited", "statutory_exception"])
def test_unknown_ambiguous_and_statutory_basis_fail_closed(basis):
    with pytest.raises(ValueError, match="cannot authorize"):
        decision(rights_basis=basis)


def test_public_facts_requires_binding_to_the_actual_sent_representation():
    with pytest.raises(ValueError, match="factual"):
        decision(rights_basis="public_facts_only", factual_representation_only=False)


def test_decision_is_artifact_and_representation_specific():
    source = {"source_artifact_id": "srcblob:a", "exact_transmitted_representation": "frozen"}
    assert require_provider_rights([decision(transmitted_representation_sha256="c" * 64)], [source])
    import hashlib
    assert not require_provider_rights([decision(transmitted_representation_sha256=hashlib.sha256(b"frozen").hexdigest())], [source])
