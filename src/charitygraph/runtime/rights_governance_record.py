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
from typing import Literal, Iterable

from pydantic import field_validator, model_validator

from ..contracts.canonical import canonical_json_bytes
from ..contracts.common import Sha256, StrictModel, require_nonblank, utc_datetime
from ..source_rights import (
    LOCAL_RETENTION_POLICY_ID,
    LOCAL_RETENTION_POLICY_VERSION,
    OPENAI_PROVIDER_POLICY_ID,
    RIGHTS_POLICY_REGISTRY,
    governed_rights_policy,
)


FORMAT_VERSION = "charitygraph.rights-governance-record/1"
SCHEMA_ID = "urn:charitygraph:builder:schema:rights-governance-record"
SCHEMA_VERSION = "1.0"

# This is the seven-basis vocabulary in the approved source-rights authority.
# It intentionally does not add a basis for a convenient local implementation.
RIGHTS_BASES = (
    "explicit_open_license",
    "explicit_terms_permission",
    "direct_permission",
    "statutory_exception",
    "public_facts_only",
    "unknown",
    "prohibited",
)
RightsBasis = Literal[
    "explicit_open_license",
    "explicit_terms_permission",
    "direct_permission",
    "statutory_exception",
    "public_facts_only",
    "unknown",
    "prohibited",
]
AxisStatus = Literal["authorized", "blocked", "unknown", "not_assessed", "revoked"]
DecisionStatus = Literal[
    "authorized", "blocked", "unknown", "revoked", "superseded", "review_required"
]
ReviewStatus = Literal[
    "current", "review_due", "under_review", "blocked", "unknown", "revoked", "superseded"
]
ActorKind = Literal["human", "automation_policy", "code"]
EventType = Literal["created", "reviewed", "superseded", "revoked", "review_due"]

_AUXILIARY_POLICY_VERSIONS = {
    LOCAL_RETENTION_POLICY_ID: LOCAL_RETENTION_POLICY_VERSION,
    # The existing provider contract carries an explicit version on each
    # decision but does not publish a local fixed-version registry entry.
    OPENAI_PROVIDER_POLICY_ID: None,
}


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
        if self.status == "authorized" and (not self.policy_id or not self.policy_version):
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

    @field_validator(
        "decision_id", "source_artifact_id", "source_record_id", "source_origin_url",
        "source_role", "rights_policy_id", "rights_policy_version", "purpose", "scope",
        "evidence_locator", "actor_id",
    )
    @classmethod
    def _required_text(cls, value: str) -> str:
        return require_nonblank(value)

    @field_validator(
        "representation_artifact_id", "provider_processing_policy_id",
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
        if governed_rights_policy(
            self.rights_policy_id,
            self.rights_policy_version,
            rights_basis=self.rights_basis,
        ) is None:
            raise RightsGovernanceError("unknown or version-mismatched rights policy identity")
        for axis in (self.local_retention, self.provider_transmission, self.public_redistribution):
            if axis.status == "authorized":
                expected_version = _AUXILIARY_POLICY_VERSIONS.get(axis.policy_id or "")
                if expected_version is None and axis.policy_id not in _AUXILIARY_POLICY_VERSIONS and axis.policy_id not in RIGHTS_POLICY_REGISTRY:
                    raise RightsGovernanceError("unknown rights-axis policy identity")
                if expected_version is not None and axis.policy_version != expected_version:
                    raise RightsGovernanceError("rights-axis policy version is unsupported")
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
    def binding_key(self) -> tuple[str, str, str, str]:
        return (self.source_artifact_id, self.source_record_id, self.source_role, str(self.representation_sha256))

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
        return self._put(raw, digest, kind="records")

    def put_event(self, event: RightsGovernanceEvent) -> Path:
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
