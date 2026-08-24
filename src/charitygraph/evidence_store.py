"""Local content-addressed storage for immutable source and derived bytes."""

from __future__ import annotations

import hashlib
import os
import tempfile
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Iterable


class ArtifactStoreError(RuntimeError):
    """Base error for content-addressed artefact storage."""


class ArtifactConflictError(ArtifactStoreError):
    """A content address or metadata identity was reused inconsistently."""


@dataclass(frozen=True)
class StoredArtifact:
    artifact_id: str
    content_hash: str
    byte_size: int
    storage_path: str
    created_at: datetime
    artifact_kind: str
    input_artifact_ids: tuple[str, ...] = ()

    @property
    def artefact_id(self) -> str:
        return self.artifact_id


class ContentAddressedArtifactStore:
    """Write bytes below a configured archive/runtime root by SHA-256.

    The store never derives identity from a filename. A SQLite catalogue may be
    supplied to index metadata and derived-input lineage, but the files remain
    the immutable evidence authority.
    """

    def __init__(self, root: str | Path, *, allowed_roots: Iterable[str | Path] = (), catalog: object | None = None) -> None:
        self.root = Path(root).expanduser().resolve()
        if not self.root.is_absolute():
            raise ArtifactStoreError("artefact root must be absolute")
        allowed = tuple(Path(item).expanduser().resolve() for item in allowed_roots)
        if allowed and not any(self.root == item or item in self.root.parents for item in allowed):
            raise ArtifactStoreError("artefact root must be below a configured archive/runtime root")
        self.catalog = catalog

    def _relative_path(self, content_hash: str) -> Path:
        if len(content_hash) != 64 or any(ch not in "0123456789abcdef" for ch in content_hash):
            raise ArtifactStoreError("content hash must be a lowercase SHA-256 value")
        relative = Path("objects") / "sha256" / content_hash[:2] / content_hash
        candidate = (self.root / relative).resolve()
        if self.root not in candidate.parents:
            raise ArtifactStoreError("unsafe artefact path")
        return relative

    def _write(self, content: bytes, content_hash: str) -> Path:
        relative = self._relative_path(content_hash)
        target = self.root / relative
        target.parent.mkdir(parents=True, exist_ok=True)
        if target.exists():
            if not target.is_file() or target.read_bytes() != content:
                raise ArtifactConflictError("content-addressed path contains different bytes")
            return target
        fd, temporary = tempfile.mkstemp(prefix=f".{content_hash}.", dir=str(target.parent))
        try:
            with os.fdopen(fd, "wb") as handle:
                handle.write(content)
                handle.flush()
                os.fsync(handle.fileno())
            try:
                os.replace(temporary, target)
            except FileExistsError:
                if target.read_bytes() != content:
                    raise ArtifactConflictError("concurrent content-addressed write disagreed")
                Path(temporary).unlink(missing_ok=True)
        finally:
            Path(temporary).unlink(missing_ok=True)
        return target

    def put(
        self,
        content: bytes,
        *,
        schema_id: str = "urn:charitygraph:builder:schema:source-artefact:1.0",
        schema_version: str = "1.0",
        artifact_kind: str = "source",
        created_at: datetime | None = None,
        input_artifact_ids: Iterable[str] = (),
    ) -> StoredArtifact:
        if not isinstance(content, (bytes, bytearray, memoryview)):
            raise ArtifactStoreError("content must be bytes")
        content = bytes(content)
        if not artifact_kind.strip() or artifact_kind not in {"source", "derived"}:
            raise ArtifactStoreError("artifact_kind must be source or derived")
        inputs = tuple(str(item) for item in input_artifact_ids)
        if len(set(inputs)) != len(inputs) or any(not item.strip() for item in inputs):
            raise ArtifactStoreError("input artefact IDs must be unique and nonblank")
        digest = hashlib.sha256(content).hexdigest()
        target = self._write(content, digest)
        timestamp = (created_at or datetime.now(timezone.utc))
        if timestamp.tzinfo is None or timestamp.utcoffset() is None:
            raise ArtifactStoreError("created_at must be timezone-aware")
        timestamp = timestamp.astimezone(timezone.utc)
        prefix = "srcblob:" if artifact_kind == "source" else "artifact:"
        artifact_id = f"{prefix}{digest}"
        stored = StoredArtifact(
            artifact_id=artifact_id,
            content_hash=digest,
            byte_size=len(content),
            storage_path=target.relative_to(self.root).as_posix(),
            created_at=timestamp,
            artifact_kind=artifact_kind,
            input_artifact_ids=inputs,
        )
        if self.catalog is not None:
            self.catalog.index_artifact(
                artifact_id=stored.artifact_id,
                content_hash=stored.content_hash,
                schema_id=schema_id,
                schema_version=schema_version,
                storage_path=stored.storage_path,
                availability="available",
                created_at=stored.created_at,
                indexed_at=stored.created_at,
            )
            if inputs:
                self.catalog.record_artifact_lineage(stored.artifact_id, inputs)
        return stored

    def put_bytes(self, content: bytes, **kwargs: object) -> StoredArtifact:
        return self.put(content, **kwargs)

    def put_file(self, path: str | Path, **kwargs: object) -> StoredArtifact:
        source = Path(path).resolve()
        if not source.is_file():
            raise ArtifactStoreError("source file does not exist")
        return self.put(source.read_bytes(), **kwargs)

    def put_derived(self, content: bytes, *, input_artifact_ids: Iterable[str], **kwargs: object) -> StoredArtifact:
        return self.put(content, artifact_kind="derived", input_artifact_ids=input_artifact_ids, **kwargs)

    def read(self, artifact: StoredArtifact | str) -> bytes:
        artifact_id = artifact.artifact_id if isinstance(artifact, StoredArtifact) else str(artifact)
        if ":" not in artifact_id:
            raise ArtifactStoreError("invalid artefact ID")
        digest = artifact_id.split(":", 1)[1]
        path = self.root / self._relative_path(digest)
        if not path.is_file():
            raise ArtifactStoreError("artefact is not available")
        content = path.read_bytes()
        if hashlib.sha256(content).hexdigest() != digest:
            raise ArtifactConflictError("stored artefact failed its content hash")
        return content

    def exists(self, artifact: StoredArtifact | str) -> bool:
        try:
            artifact_id = artifact.artifact_id if isinstance(artifact, StoredArtifact) else str(artifact)
            digest = artifact_id.split(":", 1)[1]
            return (self.root / self._relative_path(digest)).is_file()
        except (ArtifactStoreError, IndexError):
            return False
ArtefactStoreError = ArtifactStoreError
ArtefactConflictError = ArtifactConflictError
ContentAddressedArtefactStore = ContentAddressedArtifactStore
