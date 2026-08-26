"""Private runtime loader for rights-controlled CLASSIE payloads.

The loader never ships proprietary concepts in source control and never falls
back to hand-coded labels. Callers inject a lawful JSON payload at runtime.
"""
from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any, Iterable, Mapping


class PrivateClassieLoadError(ValueError):
    """Raised when a private CLASSIE payload is absent or malformed."""


def load_private_classie_payload(path: str | Path, *, expected_scheme_id: str = "classie") -> dict[str, Any]:
    payload_path = Path(path)
    try:
        raw = payload_path.read_bytes()
    except OSError as exc:
        raise PrivateClassieLoadError(f"private CLASSIE payload unavailable: {payload_path}") from exc
    content_hash = hashlib.sha256(raw).hexdigest()
    try:
        document = json.loads(raw.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise PrivateClassieLoadError("private CLASSIE payload must be UTF-8 JSON") from exc
    if not isinstance(document, Mapping):
        raise PrivateClassieLoadError("private CLASSIE payload must be an object")
    scheme_id = str(document.get("scheme_id", "")).strip()
    version = str(document.get("version", "")).strip()
    concepts = document.get("concepts")
    if not scheme_id or not version or not isinstance(concepts, list) or not concepts:
        raise PrivateClassieLoadError("private CLASSIE payload requires scheme_id, version and non-empty concepts")
    if scheme_id != expected_scheme_id:
        raise PrivateClassieLoadError("private CLASSIE payload has an unexpected scheme_id")
    normalised: list[dict[str, Any]] = []
    seen: set[str] = set()
    for row in concepts:
        if not isinstance(row, Mapping):
            raise PrivateClassieLoadError("private CLASSIE concepts must be objects")
        external_id = str(row.get("external_concept_id", "")).strip()
        label = str(row.get("preferred_label", "")).strip()
        if not external_id or not label or external_id in seen:
            raise PrivateClassieLoadError("private CLASSIE concepts require unique nonblank IDs and labels")
        seen.add(external_id)
        normalised.append({
            "external_concept_id": external_id,
            "preferred_label": label,
            "definition": row.get("definition"),
            "parent_external_concept_ids": tuple(str(item).strip() for item in row.get("parent_external_concept_ids", ()) if str(item).strip()),
        })
    return {
        "scheme_id": scheme_id,
        "version": version,
        "concepts": tuple(normalised),
        "source_locator": str(document.get("source_locator", "")).strip() or None,
        "external_scheme_id": str(document.get("external_scheme_id", "")).strip() or None,
        "content_hash": content_hash,
        "rights_policy": str(document.get("rights_policy", "")).strip() or "private_processing_approved",
        "publication_eligibility": "withheld",
        "status": "private_runtime_loaded",
    }


def public_classification_projection(assignments: Iterable[Mapping[str, Any]], *, publication_policy_id: str | None = None) -> tuple[dict[str, Any], ...]:
    """Project only assignments explicitly eligible under the requested policy.

    Publication is governed by explicit metadata. Scheme names, labels and
    lexical aliases never influence this decision.
    """
    rows: list[dict[str, Any]] = []
    for item in assignments:
        row = dict(item)
        if row.get("publication_eligibility") != "eligible":
            continue
        if publication_policy_id is not None and row.get("publication_policy_id") != publication_policy_id:
            continue
        rows.append(row)
    return tuple(rows)