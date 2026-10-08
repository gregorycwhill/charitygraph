"""Mechanical adapter for the already-retained 2026-08-10 reality-spike corpus.

This deliberately is not a discovery or acquisition adapter.  It reads the
five entries enumerated in the committed-style private source inventory,
verifies bytes against its declared SHA-256, and exposes their already-derived
JSON representations as ``RetainedCapture`` objects.  It makes no network
requests and writes no archive state.
"""
from __future__ import annotations

from datetime import datetime, timezone
from hashlib import sha256
import json
from pathlib import Path

from .contracts import ArtifactRef, EvidenceFragment, SchemaRef, SourceRecord, canonical_sha256, deterministic_id
from .retained_capture import RetainedCapture, RetainedCaptureUniverse, RetainedSubjectBinding


_SCHEMA = SchemaRef(schema_id="urn:charitygraph:builder:schema:reality-spike-retained:1.0", schema_version="1.0")
_INVENTORY = Path("processed/reality-spike/2026-08-10/source-inventory.json")
_STAMP = datetime(2026, 8, 10, tzinfo=timezone.utc)


def _sha256(path: Path) -> str:
    return sha256(path.read_bytes()).hexdigest()


def _only(paths: list[Path], label: str) -> Path:
    if len(paths) != 1:
        raise ValueError(f"retained reality-spike {label} is missing or ambiguous")
    return paths[0]


_REPORT_REPRESENTATIONS = {
    "c4f75bf25ad3481d964057cc4def56bcd23a5cf5e0b88bad616859cd8f6cb8d3": "50169561394-2022-23-financial-pages.json",
    "e8523d9595a9a7c354298d667de369b980c12f4fc3459bc222808d8e86cc0252": "13025599242-2024-25-full.json",
    "ce225c4ca50abb663922ed2eba272dbac6627d779e611ba8213f96a133adf4dd": "78126256862-2023-24-full.json",
}


def _report_representation(root: Path, source_hash: str) -> Path:
    """Use the representation explicitly bound by the retained report resolution."""
    name = _REPORT_REPRESENTATIONS.get(source_hash)
    if name is None:
        raise ValueError("annual-report source is not in the retained report-resolution inventory")
    return _only([root / name] if (root / name).is_file() else [], "annual-report representation")


def _subject_id(abn: str) -> str:
    # A private rehearsal identity, deliberately not a claimed canonical subject.
    return "subject:rehearsal:" + canonical_sha256({"scheme": "abn", "value": abn})


def _capture(archive_root: Path, item: dict[str, object]) -> RetainedCapture:
    source_hash = str(item["sha256"])
    kind = str(item["kind"])
    abn = str(dict(item["external_identifier"])["value"])
    if kind == "annual_report":
        raw = _only(list((archive_root / "sources" / "annual-reports" / abn).rglob(source_hash + ".pdf")), "annual-report blob")
        representation = _report_representation(archive_root / "processed/reality-spike/2026-08-10/report-extracts", source_hash)
    elif kind == "website_snapshot":
        raw = _only(list((archive_root / "sources" / "web" / abn).rglob(source_hash + ".html")), "website blob")
        representation = _only(list((archive_root / "processed/reality-spike/2026-08-10/web-extracts").glob(abn + "-2026-08-10.json")), "website representation")
    else:
        raise ValueError(f"unsupported retained source family: {kind}")
    if _sha256(raw) != source_hash:
        raise ValueError("retained source bytes do not match inventory SHA-256")
    rep_hash = _sha256(representation)
    source_identity = {"source_family": kind, "source_version": source_hash, "source_locator": str(item["url"]), "payload_hash": source_hash}
    source = SourceRecord(
        record_id=deterministic_id("srcrec:", source_identity), created_at=_STAMP,
        producer={"kind": "code", "producer_id": "reality-spike-retained-adapter", "version": "1"},
        source_family=kind, source_role="source-reported", source_version=source_hash,
        source_locator=str(item["url"]), retrieved_at=_STAMP, observed_at=_STAMP,
        payload_ref="srcblob:" + source_hash, payload_hash=source_hash,
    )
    payload = json.loads(representation.read_text(encoding="utf-8"))
    if kind == "annual_report":
        text = "\n".join(str(page["text"]) for page in payload["pages"] if page.get("text"))
    else:
        text = str(payload["readable_text"])
    fragment_hash = canonical_sha256({"representation_hash": rep_hash, "text": text})
    locator = representation.relative_to(archive_root).as_posix()
    fragment_identity = {"source_record_id": source.record_id, "locator": locator, "fragment_hash": fragment_hash, "selection_method": "reality-spike-retained-adapter", "selection_policy_version": "1"}
    evidence = EvidenceFragment(
        record_id=deterministic_id("evidence:", fragment_identity), created_at=_STAMP,
        producer={"kind": "code", "producer_id": "reality-spike-retained-adapter", "version": "1"},
        source_record=ArtifactRef(artifact_id=source.record_id, content_hash=source_hash, schema=_SCHEMA),
        fragment_kind="text", locator=locator, content_ref="artifact:" + rep_hash, fragment_hash=fragment_hash,
        selection_method="reality-spike-retained-adapter", selection_policy_version="1", observed_at=_STAMP,
    )
    subject_id = _subject_id(abn)
    binding = RetainedSubjectBinding(
        binding_id="binding:" + canonical_sha256({"source_record_id": source.record_id, "subject_id": subject_id, "state": "resolved", "policy_version": "reality-spike-abn-resolution-v1"}),
        source_record_id=source.record_id, subject_id=subject_id, policy_version="reality-spike-abn-resolution-v1",
    )
    return RetainedCapture(source_record=source, subject_binding=binding,
        source_blob=ArtifactRef(artifact_id="srcblob:" + source_hash, content_hash=source_hash, schema=_SCHEMA),
        representation=ArtifactRef(artifact_id="artifact:" + rep_hash, content_hash=rep_hash, schema=_SCHEMA),
        representation_input_artifact_ids=("srcblob:" + source_hash,), evidence_fragment=evidence,
        text=text, source_role="supporting")


def load_reality_spike_universes(archive_root: Path) -> tuple[RetainedCaptureUniverse, ...]:
    """Return one shared retained universe per real organisation, in ABN order."""
    inventory = json.loads((archive_root / _INVENTORY).read_text(encoding="utf-8"))
    grouped: dict[str, list[RetainedCapture]] = {}
    for item in inventory["sources"]:
        capture = _capture(archive_root, item)
        grouped.setdefault(capture.subject_binding.subject_id, []).append(capture)
    return tuple(RetainedCaptureUniverse(subject_id=subject_id, permitted_scope_ids=("scope:rehearsal:organisation",), captures=tuple(captures), packet_selection_version="reality-spike-retained-rehearsal-v1") for subject_id, captures in sorted(grouped.items()))
