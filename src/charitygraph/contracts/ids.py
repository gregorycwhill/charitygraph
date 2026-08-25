"""Opaque and documented deterministic identifiers for Builder vNext."""

from __future__ import annotations

import re
from uuid import UUID, uuid4

from .canonical import canonical_sha256
from .common import IdPrefix


_PREFIXES: tuple[IdPrefix, ...] = (
    "subject:", "subjectrecord:", "srcrec:", "evidence:", "candidate:",
    "decision:", "observation:", "assertion:", "scope:", "partyrole:",
    "relationship:", "adjudication:", "externalid:", "derivative:", "modeltask:", "modelresult:",
    "embedding:", "taskrun:", "cohort:", "pricing:", "fx:", "reservation:",
    "costledger:", "run:",
    "scheme:", "schemever:", "concept:", "mapping:", "assignment:", "programcandidate:", "semtask:",
)
_ID_RE = re.compile(r"^(?P<prefix>[a-z][a-z0-9_]*:)(?P<body>[0-9a-f]{32}|[0-9a-f]{64})$")


def new_opaque_id(prefix: IdPrefix, *, uuid_value: UUID | None = None) -> str:
    """Return a UUID4-backed ID whose body contains no subject information."""

    if prefix not in _PREFIXES:
        raise ValueError(f"unsupported ID prefix: {prefix!r}")
    value = uuid_value or uuid4()
    return f"{prefix}{value.hex}"


def deterministic_id(prefix: IdPrefix, identity: object) -> str:
    """Return a full canonical SHA-256 ID for a documented identity tuple."""

    if prefix not in _PREFIXES:
        raise ValueError(f"unsupported ID prefix: {prefix!r}")
    return f"{prefix}{canonical_sha256(identity)}"


def validate_typed_id(value: str, expected_prefix: IdPrefix | None = None) -> str:
    if not isinstance(value, str) or value != value.lower():
        raise ValueError("typed IDs must be lower-case ASCII")
    match = _ID_RE.fullmatch(value)
    if match is None or match.group("prefix") not in _PREFIXES:
        raise ValueError("malformed or uncontrolled typed ID")
    if expected_prefix is not None and match.group("prefix") != expected_prefix:
        raise ValueError(f"ID must use prefix {expected_prefix!r}")
    return value
