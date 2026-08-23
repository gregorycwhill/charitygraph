from pydantic import ValidationError
import pytest
from charitygraph.v05.models import FutureReleaseContext, PublicationIdentity, ReleaseContext


def identity():
    return PublicationIdentity(
        publisher_name="CharityGraph",
        canonical_data_repository="https://github.com/gregorycwhill/charitygraph-data",
        immutable_release_path="releases/v0.6.0-2026-08-24",
        data_license_identifier="CC-BY-4.0",
        license_url="https://creativecommons.org/licenses/by/4.0/",
        attribution_guidance="Attribute CharityGraph and link to the immutable release.",
        upstream_rights_caveat_url="https://github.com/gregorycwhill/charitygraph-data/blob/main/LICENSE",
        editorial_commitments={"identifier": "charitygraph-public-commitments", "version": "1.2-draft", "url": "https://github.com/gregorycwhill/charitygraph-data/blob/main/PUBLIC_COMMITMENTS.md"},
        producing_builder={"version": "0.2.0", "commit": "a" * 40},
    )


def test_public_contract_05_context_remains_valid_without_identity():
    context = ReleaseContext(release_id="v05", dataset_version="0.5-test", based_on_release="rc4", generated_at="2026-08-24T00:00:00Z", capability_registry={"registry_id": "registry", "path": "capability-registry.json"})
    assert context.publication_identity is None


def test_future_release_context_requires_publication_identity():
    with pytest.raises(ValidationError):
        FutureReleaseContext(release_id="future", dataset_version="0.6-test", contract_version="0.6", based_on_release="v05", generated_at="2026-08-24T00:00:00Z", capability_registry={"registry_id": "registry", "path": "capability-registry.json"})
    context = FutureReleaseContext(release_id="future", dataset_version="0.6-test", contract_version="0.6", based_on_release="v05", generated_at="2026-08-24T00:00:00Z", capability_registry={"registry_id": "registry", "path": "capability-registry.json"}, publication_identity=identity())
    assert context.publication_identity.data_license_identifier == "CC-BY-4.0"
    assert context.publication_identity.publisher_name == "CharityGraph"