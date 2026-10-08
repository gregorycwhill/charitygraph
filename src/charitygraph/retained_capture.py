"""Provider-free bridge from retained representations to bounded semantic packets.

This module deliberately accepts already captured source objects.  It neither
accepts locators for retrieval nor imports an acquisition client.  A capture is
identified by the immutable source bytes, the derived representation and the
bounded ``EvidenceFragment`` that exposes text from that representation.
"""

from __future__ import annotations

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

from .contracts import ArtifactRef, EvidenceFragment, SourceRecord, canonical_sha256
from .ethos_notability_extraction import FrozenEthosNotabilityPacket, PacketEvidence


class _Strict(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)


class RetainedSubjectBinding(_Strict):
    """A resolved, governed binding supplied by central identity machinery."""

    binding_id: str = Field(min_length=1)
    source_record_id: str = Field(min_length=1)
    subject_id: str = Field(min_length=1)
    state: Literal["resolved"] = "resolved"
    policy_version: str = Field(min_length=1)

    @model_validator(mode="after")
    def _identity_is_deterministic(self) -> "RetainedSubjectBinding":
        expected = "binding:" + canonical_sha256({
            "source_record_id": self.source_record_id,
            "subject_id": self.subject_id,
            "state": self.state,
            "policy_version": self.policy_version,
        })
        if self.binding_id != expected:
            raise ValueError("subject binding_id does not match its deterministic identity")
        return self


class RetainedCapture(_Strict):
    """One attributable bounded view over a centrally retained source version.

    ``source_blob`` is the content-addressed immutable source object named by
    ``SourceRecord.payload_ref``.  ``representation`` is a retained derived
    artefact whose declared input is that blob; the fragment's ``content_ref``
    is that representation.  The contract therefore cannot silently turn a
    locator, newly fetched body, or unlinked prose string into evidence.
    """

    source_record: SourceRecord
    subject_binding: RetainedSubjectBinding
    source_blob: ArtifactRef
    representation: ArtifactRef
    representation_input_artifact_ids: tuple[str, ...] = Field(min_length=1)
    evidence_fragment: EvidenceFragment
    text: str = Field(min_length=1)
    source_role: Literal["supporting", "corroborating", "context"]
    event_or_effective_date: str | None = None

    @model_validator(mode="after")
    def _retained_lineage_is_continuous(self) -> "RetainedCapture":
        if not self.source_blob.artifact_id.startswith("srcblob:"):
            raise ValueError("source_blob must be a retained srcblob: identity")
        if self.source_record.payload_ref != self.source_blob.artifact_id:
            raise ValueError("source_record payload_ref must identify source_blob")
        if self.source_record.payload_hash != self.source_blob.content_hash:
            raise ValueError("source_record payload_hash must match source_blob")
        if self.source_blob.artifact_id not in self.representation_input_artifact_ids:
            raise ValueError("representation must declare source_blob as an input")
        if len(set(self.representation_input_artifact_ids)) != len(self.representation_input_artifact_ids):
            raise ValueError("representation input artefact IDs must be unique")
        if self.evidence_fragment.source_record.artifact_id != self.source_record.record_id:
            raise ValueError("evidence fragment must belong to source_record")
        if self.subject_binding.source_record_id != self.source_record.record_id:
            raise ValueError("subject binding must belong to source_record")
        if self.evidence_fragment.content_ref != self.representation.artifact_id:
            raise ValueError("evidence fragment content_ref must identify representation")
        return self

    @property
    def lineage_id(self) -> str:
        """Stable identity for the exact source-object -> representation -> fragment path."""
        return "lineage:" + canonical_sha256({
            "source_record_id": self.source_record.record_id,
            "source_blob_id": self.source_blob.artifact_id,
            "source_blob_hash": self.source_blob.content_hash,
            "representation_id": self.representation.artifact_id,
            "representation_hash": self.representation.content_hash,
            "representation_inputs": self.representation_input_artifact_ids,
            "evidence_id": self.evidence_fragment.record_id,
            "fragment_hash": self.evidence_fragment.fragment_hash,
        })

    def packet_evidence(self) -> PacketEvidence:
        return PacketEvidence(
            evidence_id=self.evidence_fragment.record_id,
            source_record_id=self.source_record.record_id,
            lineage_id=self.lineage_id,
            text=self.text,
            source_role=self.source_role,
            retrieved_at=self.source_record.retrieved_at,
            event_or_effective_date=self.event_or_effective_date,
            source_family=self.source_record.source_family,
            source_version=self.source_record.source_version,
            source_locator=self.source_record.source_locator,
            source_blob_id=self.source_blob.artifact_id,
            source_blob_hash=self.source_blob.content_hash,
            representation_id=self.representation.artifact_id,
            representation_hash=self.representation.content_hash,
            representation_input_artifact_ids=self.representation_input_artifact_ids,
            fragment_locator=self.evidence_fragment.locator,
            fragment_hash=self.evidence_fragment.fragment_hash,
            selection_method=self.evidence_fragment.selection_method,
            selection_policy_version=self.evidence_fragment.selection_policy_version,
            subject_binding_id=self.subject_binding.binding_id,
            subject_binding_policy_version=self.subject_binding.policy_version,
        )


class RetainedCaptureUniverse(_Strict):
    """A subject-bound, already-acquired evidence universe for semantic work."""

    subject_id: str = Field(min_length=1)
    permitted_scope_ids: tuple[str, ...] = Field(min_length=1)
    # An empty universe is meaningful: central acquisition can explicitly say
    # that no relevant retained representation was available.  The semantic
    # worker must turn that into a coverage-gap abstention, never acquire.
    captures: tuple[RetainedCapture, ...] = ()
    packet_selection_version: str = Field(default="central-packet-selection-v1", min_length=1)

    @model_validator(mode="after")
    def _bounded_and_unique(self) -> "RetainedCaptureUniverse":
        if len(set(self.permitted_scope_ids)) != len(self.permitted_scope_ids):
            raise ValueError("permitted scope IDs must be unique")
        evidence_ids = [capture.evidence_fragment.record_id for capture in self.captures]
        if len(set(evidence_ids)) != len(evidence_ids):
            raise ValueError("retained captures must have unique evidence fragment IDs")
        for capture in self.captures:
            if capture.subject_binding.subject_id != self.subject_id:
                raise ValueError("retained capture has unresolved or conflicting subject binding")
        # An artefact identity must name one immutable content object.  This
        # catches inconsistent adapters before a packet can hide the conflict.
        for label, values in (
            ("source blob", ((c.source_blob.artifact_id, c.source_blob.content_hash) for c in self.captures)),
            ("representation", ((c.representation.artifact_id, c.representation.content_hash) for c in self.captures)),
            ("source record", ((c.source_record.record_id, c.source_record.payload_hash) for c in self.captures)),
        ):
            identities: dict[str, str] = {}
            for artifact_id, content_hash in values:
                previous = identities.setdefault(artifact_id, content_hash)
                if previous != content_hash:
                    raise ValueError(f"conflicting {label} capture identity")
        return self


def build_ethos_notability_packet(universe: RetainedCaptureUniverse) -> FrozenEthosNotabilityPacket:
    """Construct the existing CG347 packet solely from retained captures.

    Ordering is supplied by central evidence preparation and is hashed as part
    of the packet.  This is mechanical packet construction, not relevance
    assessment, source discovery, acquisition, or semantic interpretation.
    """
    evidence = tuple(capture.packet_evidence() for capture in universe.captures)
    packet_material = {
        "contract_id": "ethos-notability-extraction-v1",
        "subject_id": universe.subject_id,
        "permitted_scope_ids": universe.permitted_scope_ids,
        "packet_selection_version": universe.packet_selection_version,
        "evidence": [item.model_dump(mode="json") for item in evidence],
    }
    packet_hash = canonical_sha256(packet_material)
    return FrozenEthosNotabilityPacket(
        packet_id="packet:" + packet_hash,
        packet_hash=packet_hash,
        subject_id=universe.subject_id,
        permitted_scope_ids=universe.permitted_scope_ids,
        evidence=evidence,
        packet_selection_version=universe.packet_selection_version,
    )
