"""Single canonical JSON and content-hash authority for PR2 contracts."""

from __future__ import annotations

import hashlib
import hmac
import json
import math
import unicodedata
from datetime import date, datetime, timezone
from decimal import Decimal
from enum import Enum
from pathlib import Path
from typing import Iterable

from pydantic import BaseModel

from .common import ArtifactRecord, JsonValue


def _decimal_text(value: Decimal) -> str:
    if not value.is_finite():
        raise ValueError("non-finite Decimal values cannot be canonicalised")
    if value == 0:
        return "0"
    return format(value.normalize(), "f")


def _canonical(value: object, *, excluded: set[str], root: bool = False) -> JsonValue:
    if value is None or isinstance(value, bool):
        return value
    if isinstance(value, int):
        return value
    if isinstance(value, float):
        if not math.isfinite(value):
            raise ValueError("non-finite floats cannot be canonicalised")
        raise TypeError("binary floats are not permitted in canonical values")
    if isinstance(value, Decimal):
        return _decimal_text(value)
    if isinstance(value, datetime):
        if value.tzinfo is None or value.utcoffset() is None:
            raise ValueError("naive datetimes cannot be canonicalised")
        utc = value.astimezone(timezone.utc)
        text = utc.isoformat(timespec="microseconds").replace("+00:00", "Z")
        return text.rstrip("0").rstrip(".").replace(".", ".") if "." in text else text
    if isinstance(value, date):
        return value.isoformat()
    if isinstance(value, Enum):
        return _canonical(value.value, excluded=set())
    if isinstance(value, Path):
        raise TypeError("paths cannot be canonicalised")
    if isinstance(value, BaseModel):
        value = value.model_dump(mode="python")
    if isinstance(value, dict):
        normalised: dict[str, JsonValue] = {}
        for key, item in value.items():
            if not isinstance(key, str):
                raise TypeError("canonical object keys must be strings")
            key_text = unicodedata.normalize("NFC", key)
            if root and key_text in excluded:
                continue
            if key_text in normalised:
                raise ValueError("canonical object keys collide after NFC normalisation")
            normalised[key_text] = _canonical(item, excluded=set(), root=False)
        return {key: normalised[key] for key in sorted(normalised)}
    if isinstance(value, (list, tuple)):
        return [_canonical(item, excluded=set(), root=False) for item in value]
    if isinstance(value, (set, frozenset)):
        raise TypeError("unordered collections cannot be canonicalised")
    if isinstance(value, str):
        return unicodedata.normalize("NFC", value)
    if isinstance(value, Iterable):
        raise TypeError("arbitrary iterables cannot be canonicalised")
    raise TypeError(f"unsupported canonical value: {type(value).__name__}")


def canonical_data(value: object, *, exclude: set[str] | None = None) -> JsonValue:
    return _canonical(value, excluded=exclude or set(), root=True)


def canonical_json_bytes(value: object, *, exclude: set[str] | None = None) -> bytes:
    data = canonical_data(value, exclude=exclude)
    return json.dumps(data, ensure_ascii=False, separators=(",", ":"), sort_keys=True).encode("utf-8")


def canonical_sha256(value: object, *, exclude: set[str] | None = None) -> str:
    return hashlib.sha256(canonical_json_bytes(value, exclude=exclude)).hexdigest()


def seal_record(record: ArtifactRecord) -> ArtifactRecord:
    expected = canonical_sha256(record, exclude={"content_hash"})
    if record.content_hash is not None and record.content_hash != expected:
        raise ValueError("record already carries a different content hash")
    return record.model_copy(update={"content_hash": expected})


def verify_record_hash(record: ArtifactRecord) -> bool:
    if record.content_hash is None:
        return False
    try:
        expected = canonical_sha256(record, exclude={"content_hash"})
    except (TypeError, ValueError):
        return False
    return hmac.compare_digest(record.content_hash, expected)
