import json
import os
from pathlib import Path

import pytest
from pydantic import ValidationError

from charitygraph.publication_identity import FutureReleaseContext, PublicationIdentity
from charitygraph.v05.models import ReleaseContext


def identity(**overrides):
    values = {
        "publisher_name": "CharityGraph",
        "canonical_data_repository": "https://github.com/gregorycwhill/charitygraph-data",
        "immutable_release_path": "releases/v0.6.0-2026-08-24",
        "data_license_identifier": "CC-BY-4.0",
        "license_url": "https://creativecommons.org/licenses/by/4.0/",
        "attribution_guidance": "Attribute CharityGraph and link to the immutable release.",
        "upstream_rights_caveat_url": "https://github.com/gregorycwhill/charitygraph-data/blob/main/LICENSE",
        "editorial_commitments": {
            "identifier": "charitygraph-public-commitments",
            "version": "1.2-draft",
            "url": "https://github.com/gregorycwhill/charitygraph-data/blob/main/PUBLIC_COMMITMENTS.md",
        },
        "producing_builder": {"version": "0.2.0", "commit": "a" * 40},
    }
    values.update(overrides)
    return PublicationIdentity(**values)


def future_context(**overrides):
    values = {
        "release_id": "future",
        "dataset_version": "0.6-test",
        "contract_version": "0.6",
        "based_on_release": "v05",
        "generated_at": "2026-08-24T00:00:00Z",
        "capability_registry": {"registry_id": "registry", "path": "capability-registry.json"},
        "publication_identity": identity(),
    }
    values.update(overrides)
    return FutureReleaseContext(**values)


def test_v05_context_remains_valid_without_future_identity():
    context = ReleaseContext(
        release_id="v05",
        dataset_version="0.5-test",
        based_on_release="rc4",
        generated_at="2026-08-24T00:00:00Z",
        capability_registry={"registry_id": "registry", "path": "capability-registry.json"},
    )
    assert context.contract_version == "0.5"


def test_v05_context_rejects_future_identity_as_extra_field():
    with pytest.raises(ValidationError):
        ReleaseContext(
            release_id="v05",
            dataset_version="0.5-test",
            based_on_release="rc4",
            generated_at="2026-08-24T00:00:00Z",
            capability_registry={},
            publication_identity=identity(),
        )


def test_future_identity_and_context_accept_valid_fixture():
    result = future_context()
    assert result.publication_identity.publisher_name == "CharityGraph"
    assert result.publication_identity.producing_builder.commit == "a" * 40


@pytest.mark.parametrize(
    "field,value",
    [
        ("canonical_data_repository", "https://example.invalid/data"),
        ("immutable_release_path", "releases/../private"),
        ("immutable_release_path", "C:/release"),
        ("license_url", "not-a-url"),
        ("upstream_rights_caveat_url", "http://example.invalid/license"),
        ("attribution_guidance", ""),
        ("producing_builder", {"version": "0.2.0", "commit": "NOT-HEX"}),
    ],
)
def test_future_identity_rejects_invalid_fields(field, value):
    values = {
        "publisher_name": "CharityGraph",
        "canonical_data_repository": "https://github.com/gregorycwhill/charitygraph-data",
        "immutable_release_path": "releases/v0.6.0-2026-08-24",
        "data_license_identifier": "CC-BY-4.0",
        "license_url": "https://creativecommons.org/licenses/by/4.0/",
        "attribution_guidance": "Attribute CharityGraph.",
        "upstream_rights_caveat_url": "https://github.com/gregorycwhill/charitygraph-data/blob/main/LICENSE",
        "editorial_commitments": {"identifier": "commitments", "version": "1", "url": "https://example.invalid/commitments"},
        "producing_builder": {"version": "0.2.0", "commit": None},
    }
    values[field] = value
    with pytest.raises(ValidationError):
        PublicationIdentity(**values)


def test_future_context_rejects_contract_05():
    with pytest.raises(ValidationError):
        future_context(contract_version="0.5")


def test_serialised_identity_fields_agree_with_data_schema():
    data_root = Path(os.environ.get("CHARITYGRAPH_DATA_REPOSITORY", Path(__file__).resolve().parents[2] / "charitygraph-data"))
    schema = json.loads((data_root / "schemas/future/release-manifest.schema.json").read_text(encoding="utf-8"))
    expected = set(schema["properties"]["publication_identity"]["properties"])
    assert set(identity().model_dump()) == expected