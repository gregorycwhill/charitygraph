"""Typed, canonical authority and compilation for S0 locator crossings.

This is deliberately a small control-plane contract.  It is not an adapter for
the historical ``execution_authority`` string: a new live locator attempt must
present this material and its digest at every boundary.
"""
from __future__ import annotations

from dataclasses import asdict, dataclass
from decimal import Decimal
from hashlib import sha256
import json
from typing import Any, Mapping, Sequence

from .scale_s0 import ScalePreflightError, locator_search_request_body_sha256, validate_locator_subject_reference

SCHEMA = "urn:charitygraph:s0:locator-execution-authority"
VERSION = 1
SCOPE = "s0_locator_only"


def canonical_json(value: Any) -> str:
    """The one UTF-8 canonical representation used for authority hashes."""
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False)


def canonical_sha256(value: Any) -> str:
    return sha256(canonical_json(value).encode("utf-8")).hexdigest()


@dataclass(frozen=True)
class GovernedLocatorBinding:
    locator_subject_ref: str
    identifier_scheme: str
    identifier_value: str

    def validate(self) -> None:
        if self.identifier_scheme != "ABN":
            raise ScalePreflightError("S0 locator authority currently requires ABN external identifiers")
        validate_locator_subject_reference(locator_subject_ref=self.locator_subject_ref,
                                           locator_identifier_scheme=self.identifier_scheme,
                                           locator_identifier_value=self.identifier_value)


@dataclass(frozen=True)
class LocatorAuthorityMaterial:
    authority_id: str
    attempt_id: str
    run_id: str
    builder_commit_sha: str
    data_merge_sha: str
    provider_project: str
    frozen_material_sha256: str
    subject_bindings: tuple[GovernedLocatorBinding, ...]
    max_physical_calls: int
    per_subject_max_usd: str
    max_new_exposure_usd: str
    schema: str = SCHEMA
    version: int = VERSION
    scope: str = SCOPE

    def material(self) -> dict[str, Any]:
        return {"schema": self.schema, "version": self.version, "scope": self.scope,
                "authority_id": self.authority_id, "attempt_id": self.attempt_id, "run_id": self.run_id,
                "builder_commit_sha": self.builder_commit_sha, "data_merge_sha": self.data_merge_sha,
                "provider_project": self.provider_project, "frozen_material_sha256": self.frozen_material_sha256,
                "subject_bindings": [asdict(x) for x in self.subject_bindings],
                "budget": {"max_physical_calls": self.max_physical_calls,
                           "per_subject_max_usd": self.per_subject_max_usd,
                           "max_new_exposure_usd": self.max_new_exposure_usd}}

    @property
    def hash(self) -> str:
        self.validate()
        return canonical_sha256(self.material())

    def validate(self) -> None:
        if self.schema != SCHEMA or self.version != VERSION or self.scope != SCOPE:
            raise ScalePreflightError("unsupported S0 structured execution authority")
        if any(not isinstance(x, str) or not x for x in (self.authority_id, self.attempt_id, self.run_id,
                                                          self.builder_commit_sha, self.data_merge_sha,
                                                          self.provider_project)):
            raise ScalePreflightError("structured execution authority has an absent binding")
        if len(self.builder_commit_sha) != 40 or len(self.data_merge_sha) != 40 or len(self.frozen_material_sha256) != 64:
            raise ScalePreflightError("structured execution authority has an invalid immutable SHA")
        if not self.subject_bindings or len({x.locator_subject_ref for x in self.subject_bindings}) != len(self.subject_bindings):
            raise ScalePreflightError("structured execution authority has duplicate or absent subjects")
        for binding in self.subject_bindings:
            binding.validate()
        try:
            per_subject, total = Decimal(self.per_subject_max_usd), Decimal(self.max_new_exposure_usd)
        except Exception as error:
            raise ScalePreflightError("structured execution authority has invalid USD budget") from error
        if self.max_physical_calls != len(self.subject_bindings) or per_subject <= 0 or total != per_subject * len(self.subject_bindings):
            raise ScalePreflightError("authority call-count and exposure budget do not prove one call per subject")


@dataclass(frozen=True)
class FrozenLocatorQueries:
    binding: GovernedLocatorBinding
    queries: tuple[str, ...]

    def material(self) -> dict[str, Any]:
        return {"binding": asdict(self.binding), "queries": list(self.queries)}

    def validate(self) -> None:
        self.binding.validate()
        if not self.queries or any(not isinstance(q, str) or not q for q in self.queries):
            raise ScalePreflightError("frozen locator material has no exact query candidates")


@dataclass(frozen=True)
class CompiledLocatorSlot:
    locator_subject_ref: str
    identifier_scheme: str
    identifier_value: str
    executable_query: str
    executable_query_index: int
    executable_body_sha256: str
    alternate_queries: tuple[str, ...]
    alternate_status: str = "non_executable_requires_distinct_authority"


@dataclass(frozen=True)
class CompiledLocatorAuthority:
    authority: LocatorAuthorityMaterial
    slots: tuple[CompiledLocatorSlot, ...]

    @property
    def max_physical_calls(self) -> int: return len(self.slots)
    @property
    def max_new_exposure_usd(self) -> Decimal: return Decimal(self.authority.max_new_exposure_usd)


def frozen_locator_material_sha256(subjects: Sequence[FrozenLocatorQueries]) -> str:
    return canonical_sha256({"schema": "urn:charitygraph:s0:frozen-locator-queries", "version": 1,
                             "subjects": [x.material() for x in subjects]})


def compile_locator_authority(authority: LocatorAuthorityMaterial,
                              subjects: Sequence[FrozenLocatorQueries]) -> CompiledLocatorAuthority:
    """Compile exactly one executable first query per authority-bound subject."""
    authority.validate()
    for subject in subjects: subject.validate()
    if frozen_locator_material_sha256(subjects) != authority.frozen_material_sha256:
        raise ScalePreflightError("frozen locator material SHA does not match structured authority")
    bindings = tuple(x.binding for x in subjects)
    if bindings != authority.subject_bindings:
        raise ScalePreflightError("frozen subject bindings are substituted, reordered, or crossed")
    slots = tuple(CompiledLocatorSlot(x.binding.locator_subject_ref, x.binding.identifier_scheme,
                                      x.binding.identifier_value, x.queries[0], 0,
                                      locator_search_request_body_sha256(x.queries[0]), x.queries[1:]) for x in subjects)
    if len(slots) != authority.max_physical_calls:
        raise ScalePreflightError("compiled locator slots exceed authority call count")
    return CompiledLocatorAuthority(authority, slots)


def compile_live_locator_packets(*, mandate: Any, execution_attempt: Any, pricing: Any,
                                 frozen_at: str, authority: LocatorAuthorityMaterial,
                                 subjects: Sequence[FrozenLocatorQueries]) -> tuple[Any, ...]:
    """The sole production packet compiler for structured locator attempts."""
    compiled = compile_locator_authority(authority, subjects)
    if execution_attempt.attempt_id != authority.attempt_id or execution_attempt.run_id != authority.run_id:
        raise ScalePreflightError("structured authority cannot compile packets for another attempt/run")
    if str(pricing.estimated_provider_cost) != authority.per_subject_max_usd:
        raise ScalePreflightError("pricing exceeds or differs from structured per-subject authority")
    from .s0_locator_discovery import freeze_locator_search_packet
    return tuple(freeze_locator_search_packet(mandate=mandate, execution_attempt=execution_attempt,
                 locator_subject_ref=slot.locator_subject_ref, locator_abn=slot.identifier_value,
                 query=slot.executable_query, query_index=slot.executable_query_index, pricing=pricing,
                 frozen_at=frozen_at, provider_account_project=authority.provider_project,
                 execution_authority=authority.hash, structured_authority=authority) for slot in compiled.slots)


def validate_live_bindings(authority: LocatorAuthorityMaterial, *, attempt_id: str, run_id: str,
                           builder_commit_sha: str, data_merge_sha: str, provider_project: str) -> None:
    """Compare every external/durable live binding before reservation or send."""
    authority.validate()
    if (authority.attempt_id, authority.run_id, authority.builder_commit_sha, authority.data_merge_sha,
        authority.provider_project) != (attempt_id, run_id, builder_commit_sha, data_merge_sha, provider_project):
        raise ScalePreflightError("structured authority live binding substitution")


def structured_authority_from_material(value: Mapping[str, Any]) -> LocatorAuthorityMaterial:
    """Strict decoder; legacy opaque strings intentionally cannot enter here."""
    try:
        budget = value["budget"]
        result = LocatorAuthorityMaterial(authority_id=value["authority_id"], attempt_id=value["attempt_id"],
            run_id=value["run_id"], builder_commit_sha=value["builder_commit_sha"], data_merge_sha=value["data_merge_sha"],
            provider_project=value["provider_project"], frozen_material_sha256=value["frozen_material_sha256"],
            subject_bindings=tuple(GovernedLocatorBinding(**x) for x in value["subject_bindings"]),
            max_physical_calls=budget["max_physical_calls"], per_subject_max_usd=budget["per_subject_max_usd"],
            max_new_exposure_usd=budget["max_new_exposure_usd"], schema=value["schema"], version=value["version"], scope=value["scope"])
    except (KeyError, TypeError) as error:
        raise ScalePreflightError("legacy or incomplete authority cannot enter structured live compilation") from error
    result.validate()
    return result
