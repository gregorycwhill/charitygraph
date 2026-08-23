"""Future publication identity contract, kept outside the public v0.5 package."""
from __future__ import annotations

import re
from urllib.parse import urlparse

from pydantic import BaseModel, ConfigDict, Field, field_validator

_CANONICAL_DATA_REPOSITORY = "https://github.com/gregorycwhill/charitygraph-data"
_RELEASE_PATH = re.compile(r"^releases/[A-Za-z0-9][A-Za-z0-9._-]*$")
_COMMIT = re.compile(r"^[0-9a-f]{7,64}$")


class FutureModel(BaseModel):
    model_config = ConfigDict(extra="forbid")


class EditorialCommitments(FutureModel):
    identifier: str = Field(min_length=1)
    version: str = Field(min_length=1)
    url: str

    @field_validator("url")
    @classmethod
    def valid_url(cls, value: str) -> str:
        _require_https_url(value)
        return value


class BuilderProvenance(FutureModel):
    version: str = Field(min_length=1)
    commit: str | None = None

    @field_validator("commit")
    @classmethod
    def valid_commit(cls, value: str | None) -> str | None:
        if value is not None and not _COMMIT.fullmatch(value):
            raise ValueError("producing commit must be 7-64 lowercase hexadecimal characters")
        return value


class PublicationIdentity(FutureModel):
    publisher_name: str = "CharityGraph"
    canonical_data_repository: str = _CANONICAL_DATA_REPOSITORY
    immutable_release_path: str
    data_license_identifier: str = "CC-BY-4.0"
    license_url: str
    attribution_guidance: str = Field(min_length=1)
    upstream_rights_caveat_url: str
    editorial_commitments: EditorialCommitments
    producing_builder: BuilderProvenance

    @field_validator("publisher_name")
    @classmethod
    def fixed_publisher(cls, value: str) -> str:
        if value != "CharityGraph":
            raise ValueError("publisher_name must be CharityGraph")
        return value

    @field_validator("canonical_data_repository")
    @classmethod
    def fixed_repository(cls, value: str) -> str:
        if value != _CANONICAL_DATA_REPOSITORY:
            raise ValueError("canonical_data_repository must be the official Data repository")
        return value

    @field_validator("immutable_release_path")
    @classmethod
    def safe_release_path(cls, value: str) -> str:
        if not _RELEASE_PATH.fullmatch(value):
            raise ValueError("immutable_release_path must name one repository-relative release directory")
        return value

    @field_validator("data_license_identifier")
    @classmethod
    def fixed_license(cls, value: str) -> str:
        if value != "CC-BY-4.0":
            raise ValueError("data_license_identifier must be CC-BY-4.0")
        return value

    @field_validator("license_url", "upstream_rights_caveat_url")
    @classmethod
    def valid_urls(cls, value: str) -> str:
        _require_https_url(value)
        return value


class FutureReleaseContext(FutureModel):
    release_id: str = Field(min_length=1)
    dataset_version: str = Field(min_length=1)
    contract_version: str = Field(min_length=1)
    based_on_release: str = Field(min_length=1)
    generated_at: str = Field(min_length=1)
    capability_registry: dict[str, str]
    publication_identity: PublicationIdentity

    @field_validator("contract_version")
    @classmethod
    def not_v05(cls, value: str) -> str:
        if value == "0.5":
            raise ValueError("future release context cannot use contract 0.5")
        return value


def _require_https_url(value: str) -> None:
    parsed = urlparse(value)
    if parsed.scheme != "https" or not parsed.netloc or any(char.isspace() for char in value):
        raise ValueError("URL must be an absolute HTTPS URL")


__all__ = ["BuilderProvenance", "EditorialCommitments", "FutureReleaseContext", "PublicationIdentity"]