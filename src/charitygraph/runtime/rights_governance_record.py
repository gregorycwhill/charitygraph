"""Private content-addressed authority for artifact-bound rights records.

This module is deliberately a substrate, not a rights adjudicator.  It uses
the field names and affirmative/closed vocabulary of ``ArtifactRightsDecision``
but does not change the substantive policy registry.  Canonical record bytes
are the authority; a caller may keep a rebuildable SQLite index separately.

No path is selected or touched at import time.  Storage is used only after a
caller supplies a private absolute root explicitly.
"""

from __future__ import annotations

import hashlib
import json
import os
import stat
import tempfile
from datetime import date, datetime, timezone
from pathlib import Path
from typing import Iterable, Literal, get_args

from pydantic import StrictInt, field_validator, model_validator

from ..contracts.canonical import canonical_json_bytes
from ..contracts.common import Sha256, StrictModel, require_nonblank, utc_datetime
from .. import source_rights as source_rights_authority
from ..source_rights import (
    ArtifactRightsDecision,
    BoundedLocalRetentionDecision,
    LOCAL_RETENTION_POLICY_ID,
    LOCAL_RETENTION_POLICY_VERSION,
    OPENAI_PROVIDER_POLICY_ID,
    RIGHTS_POLICY_REGISTRY,
    RepresentationClass,
    RightsBasis as SourceRightsBasis,
)


FORMAT_VERSION = "charitygraph.rights-governance-record/1"
SCHEMA_ID = "urn:charitygraph:builder:schema:rights-governance-record"
SCHEMA_VERSION = "1.0"

# Keep the vocabulary and representation class owned by source_rights.py.  The
# runtime record is a content-addressed binding/provenance substrate; it must
# not grow a second substantive rights-policy authority.
RIGHTS_BASES = get_args(SourceRightsBasis)
RightsBasis = SourceRightsBasis
AxisStatus = Literal["authorized", "blocked", "unknown", "not_assessed", "revoked"]
DecisionStatus = Literal[
    "authorized", "blocked", "unknown", "revoked", "superseded", "review_required"
]
ReviewStatus = Literal[
    "current", "review_due", "under_review", "blocked", "unknown", "revoked", "superseded"
]
ActorKind = Literal["human", "automation_policy", "code"]
EventType = Literal["created", "reviewed", "superseded", "revoked", "review_due"]

class RightsGovernanceError(ValueError):
    """Base fail-closed error for records, history, and private storage."""


class RightsStorageError(RightsGovernanceError):
    """A private-root, byte-integrity, or content-address collision failure."""


class RightsAxis(StrictModel):
    """One independently adjudicated retention/transmission/publication axis."""

    status: AxisStatus
    policy_id: str | None = None
    policy_version: str | None = None
    decision_id: str | None = None

    @field_validator("policy_id", "policy_version", "decision_id")
    @classmethod
    def _optional_nonblank(cls, value: str | None) -> str | None:
        return None if value is None else require_nonblank(value)

    @model_validator(mode="after")
    def _metadata_matches_status(self) -> "RightsAxis":
        if self.status == "authorized" and (
            not self.policy_id or not self.policy_version or not self.decision_id
        ):
            raise RightsGovernanceError("authorized rights axis requires policy identity and version")
        if self.decision_id is not None and self.status == "not_assessed":
            raise RightsGovernanceError("not_assessed rights axis cannot carry a decision identity")
        return self


class RightsGovernanceRecord(StrictModel):
    """One immutable, exact-representation-bound rights governance record.

    ``record_id`` is derived from ``canonical_bytes`` and is not an independent
    caller-chosen identifier.  The three axis objects are intentionally
    separate: no axis is inferred from another axis or from the rights basis.
    """

    record_id: Sha256 | None = None
    decision_id: str
    source_artifact_id: str
    source_record_id: str
    subject_id: str
    source_origin_url: str
    source_role: str
    acquisition_lineage_ids: tuple[str, ...]
    representation_artifact_id: str | None = None
    representation_sha256: Sha256
    rights_basis: RightsBasis
    rights_policy_id: str
    rights_policy_version: str
    provider_processing_policy_id: str | None = None
    provider_processing_policy_version: str | None = None
    purpose: str
    scope: str
    evidence_locator: str
    evidence_sha256: Sha256
    assessed_on: date
    local_retention: RightsAxis
    provider_transmission: RightsAxis
    public_redistribution: RightsAxis
    status: DecisionStatus
    review_status: ReviewStatus
    expires_on: date | None = None
    supersedes_record_id: Sha256 | None = None
    revokes_record_id: Sha256 | None = None
    actor_kind: ActorKind
    actor_id: str
    actor_version: str | None = None
    recorded_at: datetime
    attribution: str | None = None
    licence_identifier: str | None = None
    licence_or_terms_url: str | None = None
    restrictions: str | None = None
    assessment_notes: str | None = None
    representation_class: RepresentationClass = "unclear"
    factual_representation_only: bool = False
    publicly_accessible_without_circumvention: bool | None = None
    access_controls_bypassed: bool | None = None
    lawfully_acquired: bool | None = None
    lawful_access_confirmed: bool | None = None
    analytical_purpose: str | None = None
    explicit_prohibition_found: bool = False
    provider_no_training_default: bool = False
    provider_data_sharing_opt_in: bool | None = None
    selected_page_count: StrictInt | None = None
    source_page_count: StrictInt | None = None
    one_source_native_entity_record: bool = False
    circumvention_used: bool | None = None
    retention_lifecycle_status: Literal["active_until_review", "review_due", "deleted", "blocked"] | None = None
    retention_review_due_on: date | None = None

    @field_validator(
        "decision_id", "source_artifact_id", "source_record_id", "subject_id", "source_origin_url",
        "source_role", "rights_policy_id", "rights_policy_version", "purpose", "scope",
        "evidence_locator", "actor_id",
    )
    @classmethod
    def _required_text(cls, value: str) -> str:
        return require_nonblank(value)

    @field_validator(
        "representation_artifact_id", "provider_processing_policy_id", "analytical_purpose",
        "provider_processing_policy_version", "actor_version", "attribution",
        "licence_identifier", "licence_or_terms_url", "restrictions", "assessment_notes",
    )
    @classmethod
    def _optional_text(cls, value: str | None) -> str | None:
        return None if value is None else require_nonblank(value)

    @field_validator("acquisition_lineage_ids", mode="before")
    @classmethod
    def _canonical_lineage(cls, value: Iterable[str]) -> tuple[str, ...]:
        if isinstance(value, (str, bytes)):
            raise RightsGovernanceError("acquisition lineage must be a collection of IDs")
        try:
            values = tuple(require_nonblank(item, "acquisition_lineage_id") for item in value)
        except TypeError as exc:
            raise RightsGovernanceError("acquisition lineage must be a collection of IDs") from exc
        if not values or len(set(values)) != len(values):
            raise RightsGovernanceError("acquisition lineage must be non-empty and unique")
        # Lineage membership is a set-like binding in the existing decision;
        # sorting makes equivalent reordered input the same record.
        return tuple(sorted(values))

    @field_validator("recorded_at")
    @classmethod
    def _recorded_at_utc(cls, value: datetime) -> datetime:
        return utc_datetime(value)

    @model_validator(mode="after")
    def _validate_record(self) -> "RightsGovernanceRecord":
        if self.source_role.casefold() in {"unknown", "ambiguous"}:
            raise RightsGovernanceError("source role must be resolved, not unknown or ambiguous")
        if self.scope.casefold() in {"unknown", "ambiguous"}:
            raise RightsGovernanceError("scope must be resolved, not unknown or ambiguous")
        if self.rights_basis not in RIGHTS_BASES:
            raise RightsGovernanceError("unknown rights basis")
        policy = RIGHTS_POLICY_REGISTRY.get(self.rights_policy_id)
        if policy is None or policy.get("version") != self.rights_policy_version:
            raise RightsGovernanceError("unknown or version-mismatched rights policy identity")
        if policy.get("basis") != self.rights_basis:
            raise RightsGovernanceError("rights policy basis does not match the committed authority")
        self._validate_axis_identities()
        if self.status in {"blocked", "revoked", "superseded", "unknown"} and any(
            axis.status == "authorized"
            for axis in (
                self.local_retention,
                self.provider_transmission,
                self.public_redistribution,
            )
        ):
            raise RightsGovernanceError("inactive overall status cannot contain authorized rights axes")
        if self.supersedes_record_id is not None and self.revokes_record_id is not None:
            raise RightsGovernanceError("one record cannot both supersede and revoke another record")
        if (
            self.supersedes_record_id is not None
            and self.supersedes_record_id == self.record_id
        ) or (
            self.revokes_record_id is not None
            and self.revokes_record_id == self.record_id
        ):
            raise RightsGovernanceError("record cannot supersede or revoke itself")
        if self.provider_transmission.status == "authorized":
            if self.status != "authorized":
                raise RightsGovernanceError("non-authorized decision cannot authorize provider transmission")
            if self.rights_basis in {"unknown", "prohibited"}:
                raise RightsGovernanceError("unknown or prohibited basis cannot authorize provider transmission")
            if not self.provider_processing_policy_id or not self.provider_processing_policy_version:
                raise RightsGovernanceError("provider authorization requires provider policy identity and version")
            if (
                self.provider_transmission.policy_id != self.provider_processing_policy_id
                or self.provider_transmission.policy_version != self.provider_processing_policy_version
            ):
                raise RightsGovernanceError("provider axis and provider policy binding are inconsistent")
            self._validate_source_rights_authority()
        if self.local_retention.status == "authorized":
            self._validate_local_retention_authority()
        expected_review = {
            "blocked": {"blocked"},
            "unknown": {"unknown"},
            "revoked": {"revoked"},
            "superseded": {"superseded"},
            "review_required": {"under_review", "review_due"},
            "authorized": {"current", "review_due", "under_review"},
        }
        if self.review_status not in expected_review[self.status]:
            raise RightsGovernanceError("decision status and review status are inconsistent")
        if self.status in {"revoked", "superseded", "blocked", "unknown", "review_required"} and self.provider_transmission.status == "authorized":
            raise RightsGovernanceError("inactive decision cannot authorize provider transmission")
        expected = self._calculate_record_id()
        if self.record_id is not None and self.record_id != expected:
            raise RightsGovernanceError("record identity does not match canonical bytes")
        object.__setattr__(self, "record_id", expected)
        return self

    def _validate_axis_identities(self) -> None:
        for name, axis in (
            ("local retention", self.local_retention),
            ("provider transmission", self.provider_transmission),
            ("public redistribution", self.public_redistribution),
        ):
            if axis.status != "authorized":
                continue
            if axis.policy_id == LOCAL_RETENTION_POLICY_ID:
                if name != "local retention" or axis.policy_version != LOCAL_RETENTION_POLICY_VERSION:
                    raise RightsGovernanceError("local-retention policy identity or version is unsupported")
            elif axis.policy_id == OPENAI_PROVIDER_POLICY_ID:
                if name != "provider transmission":
                    raise RightsGovernanceError("provider policy identity is unsupported on this rights axis")
                self._validate_provider_policy_identity(axis)
            else:
                axis_policy = RIGHTS_POLICY_REGISTRY.get(axis.policy_id or "")
                if name != "public redistribution" or axis_policy is None or axis_policy.get("version") != axis.policy_version:
                    raise RightsGovernanceError("rights-axis policy identity or version is unsupported")
                if axis_policy.get("basis") != self.rights_basis:
                    raise RightsGovernanceError("public rights-axis policy basis is inconsistent with the committed authority")
                if axis_policy.get("public_redistribution") is False:
                    raise RightsGovernanceError("committed rights policy does not authorize public redistribution")

    def _validate_provider_policy_identity(self, axis: RightsAxis) -> None:
        """Accept provider identity only when source_rights supplies an exact mapping.

        The committed source-rights module currently exposes the provider policy
        identifier but no provider-version registry.  The runtime therefore
        fails closed instead of turning a caller-provided non-empty version into
        an independent authority or falling back to a guessed policy.
        """

        if self.provider_processing_policy_id != axis.policy_id:
            raise RightsGovernanceError("provider axis and provider policy identity are inconsistent")
        provider_registry = getattr(source_rights_authority, "PROVIDER_POLICY_REGISTRY", None)
        if not isinstance(provider_registry, dict):
            raise RightsGovernanceError(
                "committed source-rights authority has no exact provider policy version mapping"
            )
        policy = provider_registry.get(axis.policy_id)
        if not isinstance(policy, dict) or policy.get("version") != axis.policy_version:
            raise RightsGovernanceError(
                "provider policy identity or version is unsupported by the committed source-rights authority"
            )

    def _validate_source_rights_authority(self) -> None:
        provider_policy_id = self.provider_processing_policy_id
        if not provider_policy_id:
            raise RightsGovernanceError("provider authorization cannot silently select a provider policy")
        try:
            ArtifactRightsDecision(
                decision_id=self.decision_id,
                source_artifact_id=self.source_artifact_id,
                source_record_id=self.source_record_id,
                source_origin_url=self.source_origin_url,
                source_role=self.source_role,
                acquisition_lineage_ids=self.acquisition_lineage_ids,
                transmitted_representation_sha256=self.representation_sha256,
                rights_policy_id=self.rights_policy_id,
                provider_processing_policy_id=provider_policy_id,
                rights_basis=self.rights_basis,
                evidence_locator=self.evidence_locator,
                evidence_sha256=self.evidence_sha256,
                assessed_on=self.assessed_on,
                assessment_scope=self.scope,
                attribution=self.attribution,
                licence_identifier=self.licence_identifier,
                licence_or_terms_url=self.licence_or_terms_url,
                restrictions=self.restrictions,
                assessment_notes=self.assessment_notes,
                local_retention_allowed=self.local_retention.status == "authorized",
                provider_transmission_allowed=self.provider_transmission.status == "authorized",
                public_redistribution_allowed=self.public_redistribution.status == "authorized",
                factual_representation_only=self.factual_representation_only,
                representation_class=self.representation_class,
                publicly_accessible_without_circumvention=self.publicly_accessible_without_circumvention,
                access_controls_bypassed=self.access_controls_bypassed,
                lawfully_acquired=self.lawfully_acquired,
                analytical_purpose=self.analytical_purpose or self.purpose,
                explicit_prohibition_found=self.explicit_prohibition_found,
                provider_no_training_default=self.provider_no_training_default,
                provider_data_sharing_opt_in=self.provider_data_sharing_opt_in,
            )
        except Exception as exc:
            raise RightsGovernanceError("committed source-rights authority rejected the record") from exc

    def _validate_local_retention_authority(self) -> None:
        if self.local_retention.decision_id is None or self.retention_review_due_on is None:
            raise RightsGovernanceError("authorized local retention requires decision, lifecycle, and review binding")
        if self.representation_class not in {"bounded_excerpt", "structured_factual"}:
            raise RightsGovernanceError("local retention requires a supported representation class")
        if self.lawful_access_confirmed is None or self.circumvention_used is None:
            raise RightsGovernanceError("local retention requires explicit access and circumvention predicates")
        try:
            BoundedLocalRetentionDecision(
                decision_id=self.local_retention.decision_id,
                source_artifact_id=self.source_artifact_id,
                source_record_id=self.source_record_id,
                source_role=self.source_role,
                acquisition_lineage_ids=self.acquisition_lineage_ids,
                representation_sha256=self.representation_sha256,
                rights_basis=self.rights_basis,
                representation_class=self.representation_class,
                purpose=self.purpose,
                scope=self.scope,
                selected_page_count=self.selected_page_count,
                source_page_count=self.source_page_count,
                one_source_native_entity_record=self.one_source_native_entity_record,
                lawful_access_confirmed=self.lawful_access_confirmed,
                circumvention_used=self.circumvention_used,
                explicit_prohibition_found=self.explicit_prohibition_found,
                retention_status="authorized",
                lifecycle_status=self.retention_lifecycle_status or "blocked",
                review_due_on=self.retention_review_due_on,
                provider_transmission_decision_id=(
                    self.provider_transmission.decision_id
                    if self.provider_transmission.status == "authorized" else None
                ),
                provider_transmission_status=self.provider_transmission.status
                if self.provider_transmission.status in {"authorized", "blocked", "unknown", "not_assessed"}
                else "unknown",
                public_redistribution_status=(
                    "authorized_under_separate_basis"
                    if self.public_redistribution.status == "authorized" else "not_authorized"
                ),
                public_redistribution_decision_id=(
                    self.public_redistribution.decision_id
                    if self.public_redistribution.status == "authorized" else None
                ),
            )
        except Exception as exc:
            raise RightsGovernanceError("committed source-rights authority rejected local retention") from exc

    def _payload(self) -> dict[str, object]:
        return self.model_dump(mode="python", exclude={"record_id"}, by_alias=True)

    def canonical_bytes(self) -> bytes:
        envelope = {
            "format_version": FORMAT_VERSION,
            "schema_id": SCHEMA_ID,
            "schema_version": SCHEMA_VERSION,
            "record": self._payload(),
        }
        return canonical_json_bytes(envelope)

    def _calculate_record_id(self) -> str:
        return hashlib.sha256(self.canonical_bytes()).hexdigest()

    @property
    def content_hash(self) -> str:
        assert self.record_id is not None
        return self.record_id

    # Compatibility views only; the canonical payload remains versioned and
    # uses the neutral representation/axis names above.
    @property
    def transmitted_representation_sha256(self) -> str:
        return str(self.representation_sha256)

    @property
    def assessment_scope(self) -> str:
        return self.scope

    @property
    def local_retention_allowed(self) -> bool:
        return self.local_retention.status == "authorized"

    @property
    def provider_transmission_allowed(self) -> bool:
        return self.provider_transmission.status == "authorized"

    @property
    def public_redistribution_allowed(self) -> bool:
        return self.public_redistribution.status == "authorized"

    @property
    def binding_key(self) -> tuple[str, str, str, str, str, tuple[str, ...]]:
        return (
            self.subject_id,
            self.source_artifact_id,
            self.source_record_id,
            self.source_role,
            str(self.representation_sha256),
            self.acquisition_lineage_ids,
        )

    @property
    def scope_key(self) -> tuple[str, str]:
        return self.binding_key[0], self.scope

    def can_promote(self, *, as_of: date | None = None) -> bool:
        """Return whether this record is eligible for a governed caller decision.

        Equality at ``expires_on`` remains valid; only a later date is expired.
        This method does not promote anything and does not recheck a provider.
        """

        when = as_of or date.today()
        if self.status != "authorized" or self.review_status != "current":
            return False
        if (
            self.local_retention.status == "authorized"
            and self.retention_lifecycle_status in {"active_until_review", "review_due"}
            and self.retention_review_due_on is not None
            and when > self.retention_review_due_on
        ):
            return False
        return self.expires_on is None or when <= self.expires_on


class RightsGovernanceEvent(StrictModel):
    """An immutable audit event; appending it never changes record bytes."""

    event_id: Sha256 | None = None
    record_id: Sha256
    event_type: EventType
    actor_kind: ActorKind
    actor_id: str
    recorded_at: datetime
    note: str | None = None

    @field_validator("actor_id")
    @classmethod
    def _actor(cls, value: str) -> str:
        return require_nonblank(value, "actor_id")

    @field_validator("note")
    @classmethod
    def _note(cls, value: str | None) -> str | None:
        return None if value is None else require_nonblank(value, "note")

    @field_validator("recorded_at")
    @classmethod
    def _time(cls, value: datetime) -> datetime:
        return utc_datetime(value)

    @model_validator(mode="after")
    def _identity(self) -> "RightsGovernanceEvent":
        expected = hashlib.sha256(self.canonical_bytes()).hexdigest()
        if self.event_id is not None and self.event_id != expected:
            raise RightsGovernanceError("event identity does not match canonical bytes")
        object.__setattr__(self, "event_id", expected)
        return self

    def canonical_bytes(self) -> bytes:
        return canonical_json_bytes({
            "format_version": FORMAT_VERSION,
            "schema_id": f"{SCHEMA_ID}:event",
            "schema_version": SCHEMA_VERSION,
            "event": self.model_dump(mode="python", exclude={"event_id"}, by_alias=True),
        })


def export_record(record: RightsGovernanceRecord) -> bytes:
    """Export the exact authoritative bytes for one validated record."""

    return record.canonical_bytes()


def import_record(raw: bytes) -> RightsGovernanceRecord:
    """Import exactly canonical UTF-8 bytes and verify their content address."""

    if not isinstance(raw, bytes):
        raise RightsGovernanceError("record import requires bytes")
    try:
        parsed = json.loads(raw.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise RightsGovernanceError("record bytes are not valid UTF-8 canonical JSON") from exc
    if not isinstance(parsed, dict) or set(parsed) != {"format_version", "schema_id", "schema_version", "record"}:
        raise RightsGovernanceError("record envelope is malformed")
    if parsed["format_version"] != FORMAT_VERSION or parsed["schema_id"] != SCHEMA_ID or parsed["schema_version"] != SCHEMA_VERSION:
        raise RightsGovernanceError("unsupported rights record format or schema version")
    try:
        record = RightsGovernanceRecord.model_validate(parsed["record"])
        expected = record.canonical_bytes()
    except Exception as exc:
        if isinstance(exc, RightsGovernanceError):
            raise
        raise RightsGovernanceError("record payload is malformed or invalid") from exc
    if expected != raw:
        raise RightsGovernanceError("record bytes are not strict canonical UTF-8 bytes")
    return record


def export_event(event: RightsGovernanceEvent) -> bytes:
    return event.canonical_bytes()


def import_event(raw: bytes) -> RightsGovernanceEvent:
    if not isinstance(raw, bytes):
        raise RightsGovernanceError("event import requires bytes")
    try:
        parsed = json.loads(raw.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise RightsGovernanceError("event bytes are not valid UTF-8 canonical JSON") from exc
    if not isinstance(parsed, dict) or set(parsed) != {"format_version", "schema_id", "schema_version", "event"}:
        raise RightsGovernanceError("event envelope is malformed")
    if parsed["format_version"] != FORMAT_VERSION or parsed["schema_id"] != f"{SCHEMA_ID}:event" or parsed["schema_version"] != SCHEMA_VERSION:
        raise RightsGovernanceError("unsupported event format or schema version")
    try:
        event = RightsGovernanceEvent.model_validate(parsed["event"])
    except Exception as exc:
        if isinstance(exc, RightsGovernanceError):
            raise
        raise RightsGovernanceError("event payload is malformed or invalid") from exc
    if event.canonical_bytes() != raw:
        raise RightsGovernanceError("event bytes are not strict canonical UTF-8 bytes")
    return event


def _safe_hex(value: str, *, label: str) -> str:
    if len(value) != 64 or any(ch not in "0123456789abcdef" for ch in value):
        raise RightsStorageError(f"{label} must be a lowercase SHA-256 value")
    return value


def _check_component_chain(path: Path, *, allow_missing_leaf: bool = True) -> None:
    """Reject symlink/reparse redirection in every existing path component."""

    current = Path(path.anchor)
    for part in path.parts[1:]:
        current = current / part
        if not current.exists() and allow_missing_leaf:
            continue
        try:
            info = os.lstat(current)
        except FileNotFoundError:
            continue
        if stat.S_ISLNK(info.st_mode) or current.is_symlink():
            raise RightsStorageError("private rights root/path contains a symlink")


class RightsGovernanceStore:
    """Write-once record/event files below a caller-selected private root."""

    def __init__(self, private_root: str | Path) -> None:
        raw = os.fspath(private_root)
        if not isinstance(raw, str) or not os.path.isabs(raw):
            raise RightsStorageError("private rights root must be an absolute path")
        self.root = Path(os.path.abspath(raw))
        if self.root == Path(self.root.anchor) or self.root.name in {"", ".", ".."}:
            raise RightsStorageError("private rights root must be a dedicated directory")
        _check_component_chain(self.root)

    def _target(self, kind: str, digest: str) -> Path:
        if kind not in {"records", "events"}:
            raise RightsStorageError("unknown rights storage kind")
        digest = _safe_hex(digest, label="content address")
        target = self.root / kind / "sha256" / digest[:2] / f"{digest}.json"
        _check_component_chain(self.root)
        _check_component_chain(target.parent)
        if self.root not in target.parents:
            raise RightsStorageError("rights target escaped private root")
        return target

    def _put(self, raw: bytes, digest: str, *, kind: str) -> Path:
        target = self._target(kind, digest)
        target.parent.mkdir(parents=True, exist_ok=True)
        _check_component_chain(target.parent, allow_missing_leaf=False)
        if target.exists():
            info = os.lstat(target)
            if stat.S_ISLNK(info.st_mode) or target.is_symlink() or info.st_nlink != 1:
                raise RightsStorageError("existing rights object is an unsafe link")
            existing = target.read_bytes()
            if existing != raw:
                raise RightsStorageError("content-addressed rights collision or corruption")
            return target
        fd, temporary = tempfile.mkstemp(prefix=f".{digest}.", suffix=".tmp", dir=str(target.parent))
        temporary_path = Path(temporary)
        try:
            with os.fdopen(fd, "wb") as handle:
                handle.write(raw)
                handle.flush()
                os.fsync(handle.fileno())
            os.replace(temporary_path, target)
        finally:
            temporary_path.unlink(missing_ok=True)
        return target

    def put_record(self, record: RightsGovernanceRecord) -> Path:
        raw = export_record(record)
        digest = hashlib.sha256(raw).hexdigest()
        if digest != record.content_hash:
            raise RightsStorageError("record content address does not match canonical bytes")
        existing = self.restore_records()
        if any(item.content_hash == record.content_hash for item in existing):
            validate_history(existing)
        else:
            validate_history((*existing, record))
        return self._put(raw, digest, kind="records")

    def put_event(self, event: RightsGovernanceEvent) -> Path:
        record_target = self._target("records", event.record_id)
        if not record_target.is_file():
            raise RightsStorageError("rights event target record is not available")
        self.load_record(event.record_id)
        raw = export_event(event)
        digest = hashlib.sha256(raw).hexdigest()
        if digest != event.event_id:
            raise RightsStorageError("event content address does not match canonical bytes")
        return self._put(raw, digest, kind="events")

    def load_record(self, record_id: str) -> RightsGovernanceRecord:
        target = self._target("records", _safe_hex(record_id, label="record ID"))
        if not target.is_file():
            raise RightsStorageError("rights record is not available")
        info = os.lstat(target)
        if stat.S_ISLNK(info.st_mode) or info.st_nlink != 1:
            raise RightsStorageError("rights record is an unsafe link")
        raw = target.read_bytes()
        if hashlib.sha256(raw).hexdigest() != record_id:
            raise RightsStorageError("rights record failed its content hash")
        record = import_record(raw)
        if record.content_hash != record_id:
            raise RightsStorageError("rights record identity mismatch")
        return record

    def load_event(self, event_id: str) -> RightsGovernanceEvent:
        target = self._target("events", _safe_hex(event_id, label="event ID"))
        if not target.is_file():
            raise RightsStorageError("rights event is not available")
        info = os.lstat(target)
        if stat.S_ISLNK(info.st_mode) or info.st_nlink != 1:
            raise RightsStorageError("rights event is an unsafe link")
        raw = target.read_bytes()
        if hashlib.sha256(raw).hexdigest() != event_id:
            raise RightsStorageError("rights event failed its content hash")
        event = import_event(raw)
        if event.event_id != event_id:
            raise RightsStorageError("rights event identity mismatch")
        return event

    def restore_records(self) -> tuple[RightsGovernanceRecord, ...]:
        records_root = self.root / "records" / "sha256"
        if not records_root.exists():
            return ()
        _check_component_chain(records_root, allow_missing_leaf=False)
        loaded: list[RightsGovernanceRecord] = []
        for path in sorted(records_root.glob("*/*.json")):
            if path.is_symlink() or not path.is_file():
                raise RightsStorageError("rights record tree contains an unsafe entry")
            digest = path.stem
            loaded.append(self.load_record(digest))
        return tuple(sorted(loaded, key=lambda item: item.content_hash))


def validate_history(records: Iterable[RightsGovernanceRecord]) -> tuple[RightsGovernanceRecord, ...]:
    """Validate immutable supersession/revocation links and return sorted history."""

    items = tuple(records)
    by_id: dict[str, RightsGovernanceRecord] = {}
    for item in items:
        if item.content_hash in by_id:
            raise RightsGovernanceError("duplicate rights record identity")
        by_id[item.content_hash] = item
    incoming: dict[str, str] = {}
    links: dict[str, str] = {}
    for item in items:
        target = item.supersedes_record_id or item.revokes_record_id
        if target is None:
            continue
        if target not in by_id or target == item.content_hash:
            raise RightsGovernanceError("rights lifecycle link is missing or self-referential")
        prior = by_id[target]
        if prior.binding_key != item.binding_key or prior.scope != item.scope:
            raise RightsGovernanceError("rights lifecycle link crosses representation or scope")
        if target in incoming:
            raise RightsGovernanceError("rights lifecycle target has ambiguous successors")
        incoming[target] = item.content_hash
        links[item.content_hash] = target
    for start in links:
        seen: set[str] = set()
        current = start
        while current in links:
            if current in seen:
                raise RightsGovernanceError("rights lifecycle contains a cycle")
            seen.add(current)
            current = links[current]
    return tuple(sorted(items, key=lambda item: item.content_hash))


def resolve_current(
    records: Iterable[RightsGovernanceRecord],
    *,
    as_of: date | None = None,
) -> tuple[RightsGovernanceRecord, ...]:
    """Return one eligible current record per exact representation and scope.

    Unknown, expired, revoked, superseded, blocked, and review-required records
    are omitted.  Conflicting eligible records fail closed rather than being
    selected by insertion order.  This is a pure view over supplied records.
    """

    history = validate_history(records)
    revoked_or_superseded = {
        target
        for item in history
        for target in (item.supersedes_record_id, item.revokes_record_id)
        if target is not None
    }
    when = as_of or date.today()
    selected: dict[tuple[str, str, str, str, str], RightsGovernanceRecord] = {}
    for item in history:
        if item.content_hash in revoked_or_superseded or not item.can_promote(as_of=when):
            continue
        key = (*item.binding_key, item.scope)
        if key in selected:
            raise RightsGovernanceError("multiple eligible current rights records are ambiguous")
        selected[key] = item
    return tuple(selected[key] for key in sorted(selected))


__all__ = [
    "FORMAT_VERSION", "SCHEMA_ID", "SCHEMA_VERSION", "RIGHTS_BASES",
    "RightsAxis", "RightsGovernanceRecord", "RightsGovernanceEvent",
    "RightsGovernanceError", "RightsStorageError", "RightsGovernanceStore",
    "export_record", "import_record", "export_event", "import_event",
    "validate_history", "resolve_current",
]
