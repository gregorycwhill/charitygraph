"""Private runtime subject pre-registration for Section 16 experiments."""

from __future__ import annotations

from datetime import datetime

from .contracts import ArtifactRef, ExternalIdentifier, SchemaRef, SubjectRecord
from .contracts.ids import new_opaque_id
from .runtime import SQLiteCatalog


def ensure_section16_subject(
    catalog: SQLiteCatalog,
    *,
    abn: str,
    display_name: str,
    source_record_id: str,
    now: datetime,
) -> tuple[str, bool]:
    """Ensure an authoritative ABN-backed organisation anchor exists.

    This is deliberately ordinary subject registration: it uses the existing
    ABR issuer contract, an authoritative SourceRecord reference, and opaque
    UUID4 subject IDs.  It does not create an experiment-specific namespace.
    """
    normalized = " ".join(str(abn).split())
    with catalog._connection() as conn:
        row = conn.execute(
            "SELECT subject_id FROM external_identifiers WHERE scheme='ABN' "
            "AND identifier_value=? AND issuing_authority='Australian Business Register' "
            "AND status='active'",
            (normalized,),
        ).fetchone()
    if row:
        return str(row[0]), False
    source = catalog.get_source_record(source_record_id)
    if source is None:
        raise ValueError("authoritative SourceRecord is required before subject registration")
    subject_id = new_opaque_id("subject:")
    subject = SubjectRecord(
        record_id=new_opaque_id("subjectrecord:"),
        created_at=now,
        producer={"kind": "code", "producer_id": "section16-subject-registration", "version": "1"},
        subject_id=subject_id,
        subject_kind="unknown",
        lifecycle_status="active",
        display_name=display_name,
        external_identifiers=(ExternalIdentifier(
            scheme="ABN", value=normalized, issuing_authority="Australian Business Register",
            source_record_ids=(source_record_id,),
        ),),
        identity_authority_refs=(ArtifactRef(
            artifact_id=source_record_id,
            content_hash=source["payload_hash"],
            schema=SchemaRef(schema_id="urn:charitygraph:builder:schema:source-record:1.0", schema_version="1.0"),
        ),),
        identity_policy_id="acnc-registered-charity-bootstrap-v1",
    )
    catalog.register_subject(subject)
    return subject_id, True
