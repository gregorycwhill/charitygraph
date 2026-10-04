"""Rights-gated, replayable retrieval of already-approved source locations.

This module deliberately has no source-family knowledge and no discovery logic.
Callers must supply a governed source definition and an explicit rights/review
disposition before a fetched byte stream can enter the local artifact cache.
"""

from __future__ import annotations

import hashlib
import json
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from enum import Enum
from pathlib import Path
from time import sleep
from typing import Callable, Protocol
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

from ..evidence_store import ContentAddressedArtifactStore, StoredArtifact


class RightsState(str, Enum):
    APPROVED_PRODUCTION = "approved_production"
    RESEARCH_ONLY = "research_only"
    UNAPPROVED = "unapproved"


class ReviewState(str, Enum):
    APPROVED = "approved"
    PENDING = "pending"
    REJECTED = "rejected"


class AcquisitionError(RuntimeError):
    """A retrieval was not eligible to be retained as evidence."""


class _Response(Protocol):
    headers: object

    def __enter__(self): ...
    def __exit__(self, *args: object) -> None: ...
    def read(self, amount: int = -1) -> bytes: ...
    def geturl(self) -> str: ...
    def getcode(self) -> int: ...


OpenUrl = Callable[[Request, float], _Response]


@dataclass(frozen=True)
class SourceAccessDecision:
    """The source-rights decision attached to one permitted retrieval path."""

    source_definition_id: str
    source_role: str
    rights_state: RightsState
    review_state: ReviewState
    decision_id: str

    def allows(self, target: str) -> bool:
        if self.rights_state is RightsState.UNAPPROVED or self.review_state is ReviewState.REJECTED:
            return False
        if target == "production":
            return self.rights_state is RightsState.APPROVED_PRODUCTION and self.review_state is ReviewState.APPROVED
        return target == "research" and self.rights_state in {RightsState.APPROVED_PRODUCTION, RightsState.RESEARCH_ONLY}


@dataclass(frozen=True)
class CachedAcquisition:
    cache_key: str
    source_definition_id: str
    source_role: str
    requested_url: str
    resolved_url: str
    retrieved_at: str
    content_type: str
    content_sha256: str
    byte_size: int
    artifact_id: str
    stable_locator: str
    rights_state: str
    review_state: str
    decision_id: str


class AcquisitionCache:
    """Metadata-only cache index; source bytes stay in the artifact store."""

    def __init__(self, path: str | Path) -> None:
        self.path = Path(path)

    def get(self, key: str) -> CachedAcquisition | None:
        if not self.path.is_file():
            return None
        data = json.loads(self.path.read_text(encoding="utf-8"))
        record = data.get(key)
        return CachedAcquisition(**record) if record else None

    def put(self, value: CachedAcquisition) -> CachedAcquisition:
        data = json.loads(self.path.read_text(encoding="utf-8")) if self.path.is_file() else {}
        prior = data.get(value.cache_key)
        if prior and prior != asdict(value):
            raise AcquisitionError("cache key already has a different evidence identity")
        self.path.parent.mkdir(parents=True, exist_ok=True)
        temporary = self.path.with_suffix(".tmp")
        temporary.write_text(json.dumps({**data, value.cache_key: asdict(value)}, sort_keys=True), encoding="utf-8")
        temporary.replace(self.path)
        return value


def _canonical_url(url: str) -> str:
    return url if url.startswith(("https://", "http://")) else f"https://{url}"


def _cache_key(decision: SourceAccessDecision, requested_url: str, media_family: str) -> str:
    material = "\n".join((decision.source_definition_id, decision.source_role, decision.decision_id, requested_url, media_family))
    return hashlib.sha256(material.encode("utf-8")).hexdigest()


def _media_type(response: _Response) -> str:
    headers = response.headers
    getter = getattr(headers, "get_content_type", None)
    if getter:
        return str(getter()).lower()
    return str(getattr(headers, "get", lambda *_: "")("Content-Type", "")).split(";", 1)[0].lower()


def acquire_approved_source(
    url: str,
    *,
    decision: SourceAccessDecision,
    target: str,
    media_family: str,
    cache: AcquisitionCache,
    artifact_store: ContentAddressedArtifactStore,
    timeout_seconds: float = 20,
    max_bytes: int = 1_000_000,
    retries: int = 1,
    opener: OpenUrl | None = None,
    wait: Callable[[float], None] = sleep,
    now: Callable[[], datetime] = lambda: datetime.now(timezone.utc),
) -> tuple[CachedAcquisition, bool]:
    """Fetch an approved HTML/PDF location or return its verified cached identity.

    ``target`` is either ``research`` or ``production``.  Production is refused
    unless the decision is explicitly approved; this is intentionally enforced
    before any network operation.
    """
    if target not in {"research", "production"}:
        raise AcquisitionError("target must be research or production")
    if media_family not in {"html", "pdf"}:
        raise AcquisitionError("media_family must be html or pdf")
    if not decision.allows(target):
        raise AcquisitionError("source rights/review state does not permit this target")
    if timeout_seconds <= 0 or max_bytes <= 0 or retries < 0:
        raise AcquisitionError("timeout, byte bound and retries must be valid")

    requested_url = _canonical_url(url)
    key = _cache_key(decision, requested_url, media_family)
    cached = cache.get(key)
    if cached:
        try:
            content = artifact_store.read(cached.artifact_id)
        except Exception as error:
            raise AcquisitionError("cached artifact is unavailable or failed integrity verification") from error
        if hashlib.sha256(content).hexdigest() != cached.content_sha256:
            raise AcquisitionError("cached artifact identity no longer matches its receipt")
        return cached, True

    open_request = opener or (lambda request, timeout: urlopen(request, timeout=timeout))
    request = Request(requested_url, headers={"User-Agent": "CharityGraph-approved-acquisition/1"})
    last_error: str | None = None
    for attempt in range(retries + 1):
        try:
            with open_request(request, timeout_seconds) as response:
                body = response.read(max_bytes + 1)
                if len(body) > max_bytes:
                    raise AcquisitionError("response_too_large")
                content_type = _media_type(response)
                is_pdf = content_type == "application/pdf" or body.startswith(b"%PDF-")
                if (media_family == "pdf" and not is_pdf) or (media_family == "html" and content_type not in {"text/html", "application/xhtml+xml"}):
                    raise AcquisitionError(f"unsupported_content_type:{content_type or 'unknown'}")
                timestamp = now().astimezone(timezone.utc).isoformat()
                artifact: StoredArtifact = artifact_store.put(body, created_at=datetime.fromisoformat(timestamp))
                value = CachedAcquisition(
                    cache_key=key, source_definition_id=decision.source_definition_id, source_role=decision.source_role,
                    requested_url=requested_url, resolved_url=response.geturl(), retrieved_at=timestamp,
                    content_type=content_type, content_sha256=artifact.content_hash, byte_size=artifact.byte_size,
                    artifact_id=artifact.artifact_id, stable_locator=f"artifact:{artifact.content_hash}",
                    rights_state=decision.rights_state.value, review_state=decision.review_state.value,
                    decision_id=decision.decision_id,
                )
                return cache.put(value), False
        except AcquisitionError:
            raise
        except HTTPError as error:
            last_error = f"http_{error.code}"
        except (URLError, TimeoutError, OSError):
            last_error = "connection_failed"
        if attempt < retries:
            wait(0.1 * (attempt + 1))
    raise AcquisitionError(last_error or "retrieval_failed")
