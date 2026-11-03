"""Fail-closed controls for the private product-value source-only baseline.

This module validates local packet bytes and future campaign preconditions. It
does not call a provider, acquire evidence, create candidates or persist runtime
knowledge. Candidate-generation callers must invoke ``require_campaign_ready``
immediately before constructing/sending any provider request.
"""
from __future__ import annotations

import hashlib
import json
import os
import re
import shutil
import stat
import tempfile
import zipfile
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from decimal import Decimal, InvalidOperation
from pathlib import Path
from typing import Mapping, Sequence


LOCK_STATEMENT = "SOURCE_ONLY_BASELINE_LOCKED_BEFORE_NEW_CANDIDATE_GENERATION"
LOCAL_RETENTION_POLICY = "CG_BOUNDED_LOCAL_ANALYTICAL_RETENTION_V1"
LOCAL_RETENTION_VERSION = "1.0.0"
MAX_ATTEMPT_AUD = Decimal("0.25")
MAX_CAMPAIGN_AUD = Decimal("2.00")
MAX_ATTEMPTS = 5
PROVIDER_ATTESTATION_MAX_AGE = timedelta(minutes=15)
EXPECTED_ABNS = frozenset({
    "28004778081", "78053639115", "50169561394", "61002643852",
    "65159324697", "32565549842", "80009663478", "57057493017",
})
EXPECTED_SUBJECT_NAMES = {
    "28004778081": "World Vision Australia",
    "78053639115": "Bush Heritage Australia",
    "50169561394": "Australian Red Cross Society",
    "61002643852": "Greenpeace Australia Pacific",
    "65159324697": "The Sunrise Project Australia",
    "32565549842": "St George Community Housing Limited",
    "80009663478": "Royal Flying Doctor Service of Australia (Queensland Section)",
    "57057493017": "The Leukaemia Foundation of Australia Limited",
}
APPROVED_PACKET_MANIFEST_SHA256 = "7204d5e696494064691a17def69210f0ef3985dd18fccca79c746f1b277c8f9f"
APPROVED_MODEL_ASSISTED_ZIP_SHA256 = "db493574c062f1505589d273629c20202de916978388740379724d9a37ce7d15"
MODEL_ASSISTED_LOCK_STATUS = "MODEL_ASSISTED_SOURCE_ONLY_BASELINE_LOCKED_BEFORE_NEW_CANDIDATE_GENERATION"
MODEL_ASSISTED_REVIEWER_ROLE = "MODEL_ASSISTED_SOURCE_ONLY_REVIEWER"
EXPERIMENT_ID = "product-value-experiment-2026-09-14"
PROPOSED_CAPABILITY_BY_ABN = {
    "28004778081": "outcomes", "78053639115": "outcomes",
    "50169561394": "commitments", "61002643852": "commitments",
    "65159324697": "commitments",
}


class BaselineGateError(ValueError):
    """A source-only or campaign precondition failed closed."""


def _sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _read_json(path: Path) -> dict:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError) as exc:
        raise BaselineGateError(f"cannot read valid UTF-8 JSON: {path.name}") from exc
    if not isinstance(value, dict):
        raise BaselineGateError(f"expected JSON object: {path.name}")
    return value


def _relative(root: Path, value: str) -> Path:
    candidate = Path(value)
    if candidate.is_absolute() or ".." in candidate.parts:
        raise BaselineGateError(f"packet path escapes its root: {value}")
    return root / candidate


def _manifest(root: Path) -> tuple[dict, str]:
    raw = (root / "manifest.json").read_bytes()
    checksum_parts = (root / "manifest.sha256").read_text(encoding="ascii").strip().split()
    if not checksum_parts:
        raise BaselineGateError("manifest.sha256 is empty")
    expected = checksum_parts[0]
    actual = _sha256(raw)
    if not re.fullmatch(r"[0-9a-f]{64}", expected) or actual != expected:
        raise BaselineGateError("packet manifest hash does not match manifest.sha256")
    if actual != APPROVED_PACKET_MANIFEST_SHA256:
        raise BaselineGateError("packet manifest is not the product-owner-approved frozen source-only baseline")
    value = _read_json(root / "manifest.json")
    if value.get("status") != "AWAITING_HUMAN_SOURCE_ONLY_COMPLETION":
        raise BaselineGateError("packet status must remain awaiting human source-only completion")
    return value, actual


def validate_source_only_packet(packet_dir: str | Path) -> str:
    """Verify the exact fixed source universe and reject any unlisted artifact."""
    root = Path(packet_dir).resolve(strict=True)
    manifest, manifest_hash = _manifest(root)
    if manifest.get("packet_id") != "product-value-source-only-baseline-2026-09-14":
        raise BaselineGateError("unexpected packet identity")
    cohort = manifest.get("cohort", [])
    abns = [str(row.get("abn")) for row in cohort]
    if len(cohort) != 8 or set(abns) != EXPECTED_ABNS or len(set(abns)) != 8:
        raise BaselineGateError("packet cohort does not match the approved eight subjects")
    if any(row.get("name") != EXPECTED_SUBJECT_NAMES[row["abn"]] or not row.get("subject_id") for row in cohort):
        raise BaselineGateError("subject names and durable identities must match the approved cohort")
    subject_ids = {row["abn"]: row["subject_id"] for row in cohort}
    if manifest.get("analyst_identity") != "Greg" or manifest.get("analyst_role") != "HUMAN_SOURCE_ONLY_ANALYST":
        raise BaselineGateError("source-only analyst identity/role differs from the approved record")

    metadata_path = _relative(root, manifest.get("source_metadata_path", ""))
    metadata_raw = metadata_path.read_bytes()
    if _sha256(metadata_raw) != manifest.get("source_metadata_sha256"):
        raise BaselineGateError("source metadata hash mismatch")
    metadata = _read_json(metadata_path)
    metadata_rows = metadata.get("sources", [])
    metadata_by_path = {row.get("representation_path"): row for row in metadata_rows}
    if len(metadata_by_path) != len(metadata_rows):
        raise BaselineGateError("source metadata contains duplicate representation paths")
    expected_files = {"README.md", "manifest.json", "manifest.sha256", manifest["source_metadata_path"]}
    expected_files.update(manifest.get("answer_files", []))
    expected_files.update(row["path"] for row in manifest.get("sources", []))
    expected_files.update(row["path"] for row in manifest.get("task_forms", []))
    expected_files.update(f"answers/{Path(row['path']).name}" for row in manifest.get("task_forms", []))

    sources = manifest.get("sources", [])
    if len(sources) != 16 or len(metadata_rows) != 16:
        raise BaselineGateError("packet must contain the approved 16 exact source representations")
    counts: dict[str, int] = {}
    for row in sources:
        abn, rel = str(row.get("abn")), str(row.get("path"))
        counts[abn] = counts.get(abn, 0) + 1
        path = _relative(root, rel)
        raw = path.read_bytes()
        if _sha256(raw) != row.get("representation_sha256"):
            raise BaselineGateError(f"source representation hash mismatch: {rel}")
        meta = metadata_by_path.get(rel)
        if not meta or meta.get("abn") != abn or meta.get("source_artifact_id") != row.get("source_artifact_id"):
            raise BaselineGateError(f"source identity does not match its metadata: {rel}")
        if meta.get("subject_id") != subject_ids[abn]:
            raise BaselineGateError(f"source subject identity does not match the approved cohort: {rel}")
        if meta.get("representation_sha256") != row.get("representation_sha256"):
            raise BaselineGateError(f"source metadata hash does not match manifest: {rel}")
        if (meta.get("retention_status") != "authorized"
                or meta.get("retention_policy_id") != LOCAL_RETENTION_POLICY
                or meta.get("retention_policy_version") != LOCAL_RETENTION_VERSION
                or not meta.get("retention_decision_id")
                or meta.get("retention_review_due") != "2027-09-14"):
            raise BaselineGateError(f"local retention approval is missing or mismatched: {rel}")
        if meta.get("public_redistribution_status") != "not_authorized":
            raise BaselineGateError(f"public redistribution must remain unauthorized: {rel}")
        if (not meta.get("provider_rights_decision_id")
                or meta.get("provider_transmission_status") != "separately_authorized_for_exact_hash_subject_to_revalidation"):
            raise BaselineGateError(f"provider transmission rights must remain a separate decision: {rel}")
        if (meta.get("legal_scope") != "organisation" or not meta.get("source_record_id")
                or not meta.get("evidence_locator_id") or not meta.get("source_role")):
            raise BaselineGateError(f"source identity, legal scope, role or locator is incomplete: {rel}")
    if set(counts) != EXPECTED_ABNS or any(counts.get(abn) != 2 for abn in EXPECTED_ABNS):
        raise BaselineGateError("each approved subject must have exactly two source representations")

    forms = manifest.get("task_forms", [])
    if len(forms) != 11 or len(manifest.get("answer_files", [])) != 11:
        raise BaselineGateError("the eight Inspect and three Compare forms must be present")
    required_form_names = {f"inspect-{abn}.md" for abn in EXPECTED_ABNS} | {
        "compare-a-greenpeace-sunrise.md", "compare-b-world-vision-bush-heritage.md",
        "compare-c-st-george-rfds.md",
    }
    if {Path(row["path"]).name for row in forms} != required_form_names:
        raise BaselineGateError("packet task forms do not match the frozen Inspect and Compare tasks")
    for row in forms:
        path = _relative(root, row["path"])
        if _sha256(path.read_bytes()) != row.get("sha256"):
            raise BaselineGateError(f"fixed task form hash mismatch: {row['path']}")
        answer_path = _relative(root, f"answers/{path.name}")
        if not answer_path.is_file():
            raise BaselineGateError(f"missing answer form: {answer_path.name}")
        expected_files.add(f"answers/{path.name}")
        expected_files.add(row["path"])
    comparison_hashes = manifest.get("comparison_question_sha256", {})
    comparison_forms = {Path(row["path"]).name: row["sha256"] for row in forms if "compare-" in row["path"]}
    if comparison_hashes != comparison_forms or len(comparison_forms) != 3:
        raise BaselineGateError("fixed comparison-question hashes do not match the three frozen Compare forms")
    actual_files = {p.relative_to(root).as_posix() for p in root.rglob("*") if p.is_file()}
    allowed_files = expected_files | {"source-only-baseline.lock.json"}
    if actual_files - allowed_files:
        raise BaselineGateError("source-only packet contains unapproved artifacts: " + ", ".join(sorted(actual_files - allowed_files)))
    allowed_dirs: set[str] = set()
    for rel in allowed_files:
        parent = Path(rel).parent
        while parent != Path("."):
            allowed_dirs.add(parent.as_posix())
            parent = parent.parent
    actual_dirs = {p.relative_to(root).as_posix() for p in root.rglob("*") if p.is_dir()}
    if actual_dirs - allowed_dirs:
        raise BaselineGateError("source-only packet contains unapproved directories")
    return manifest_hash


def _answer_hashes(root: Path, manifest: Mapping) -> dict[str, str]:
    hashes: dict[str, str] = {}
    expected_hash = _sha256((root / "manifest.json").read_bytes())
    for rel in manifest.get("answer_files", []):
        path = _relative(root, rel)
        text = path.read_text(encoding="utf-8")
        if "**Answer status:** `COMPLETE`" not in text:
            raise BaselineGateError(f"required source-only answer is incomplete: {rel}")
        if f"**Packet manifest SHA-256:** `{expected_hash}`" not in text:
            raise BaselineGateError(f"answer is not bound to the current packet manifest: {rel}")
        if "[[REQUIRED]]" in text:
            raise BaselineGateError(f"required answer fields remain unfinished: {rel}")
        hashes[rel] = _sha256(path.read_bytes())
    if len(hashes) != 11:
        raise BaselineGateError("all eleven source-only answers are required")
    return hashes


def import_and_lock_model_assisted_baseline(
    zip_path: str | Path,
    approved_packet_dir: str | Path,
    destination_dir: str | Path,
    *,
    accepted_by: str,
    accepted_at: datetime,
) -> dict[str, str]:
    """Validate the one approved completion archive, import privately, and lock once.

    Archive bytes are fully checked in memory before the destination is created.
    The source-only subtree receives only the original packet files, completed
    answers, and the lock. The note, answer-hash list, and projection form remain
    alongside it in the private import directory.
    """
    archive_path = Path(zip_path).resolve(strict=True)
    original = Path(approved_packet_dir).resolve(strict=True)
    destination = Path(destination_dir).resolve()
    if destination.exists():
        raise BaselineGateError("model-assisted baseline destination already exists; import is one-time")
    if accepted_by != "Greg" or accepted_at.tzinfo is None or accepted_at.utcoffset() is None:
        raise BaselineGateError("a timezone-aware product-owner acceptance by Greg is required")
    if _sha256(archive_path.read_bytes()) != APPROVED_MODEL_ASSISTED_ZIP_SHA256:
        raise BaselineGateError("completed ZIP does not match the specifically approved model-assisted archive")

    manifest_hash = validate_source_only_packet(original)
    manifest, _ = _manifest(original)
    prefix = "product-value-baseline-2026-09-14-model-assisted-completed/"
    try:
        with zipfile.ZipFile(archive_path, "r") as archive:
            infos = archive.infolist()
            names = [info.filename for info in infos]
            if len(names) != len(set(names)) or any(info.is_dir() for info in infos):
                raise BaselineGateError("completed ZIP has duplicate entries or unexpected directories")
            if sum(info.file_size for info in infos) > 1_000_000 or len(infos) > 64:
                raise BaselineGateError("completed ZIP exceeds the fixed packet size or file-count bound")
            archive_files: dict[str, bytes] = {}
            for info in infos:
                posix = Path(info.filename.replace("\\", "/"))
                if (not info.filename.startswith(prefix) or posix.is_absolute()
                        or ".." in posix.parts or stat.S_ISLNK(info.external_attr >> 16)):
                    raise BaselineGateError("completed ZIP contains an unsafe or unexpected path")
                relative = info.filename[len(prefix):]
                if not relative:
                    raise BaselineGateError("completed ZIP contains an empty path")
                archive_files[relative] = archive.read(info)
    except (OSError, zipfile.BadZipFile, RuntimeError) as exc:
        raise BaselineGateError("completed ZIP is unreadable or corrupt") from exc

    packet_files = {"source-only/README.md", "source-only/manifest.json", "source-only/manifest.sha256",
                    "source-only/" + manifest["source_metadata_path"]}
    packet_files.update("source-only/" + row["path"] for row in manifest["sources"])
    packet_files.update("source-only/" + row["path"] for row in manifest["task_forms"])
    packet_files.update("source-only/" + rel for rel in manifest["answer_files"])
    allowed_archive_files = packet_files | {
        "MODEL_ASSISTED_ANSWER_HASHES.json", "MODEL_ASSISTED_COMPLETION_NOTE.md",
        "projection-evaluation/PROJECTION_REVIEW_FORM.md",
    }
    if set(archive_files) != allowed_archive_files:
        extra = sorted(set(archive_files) - allowed_archive_files)
        missing = sorted(allowed_archive_files - set(archive_files))
        raise BaselineGateError(f"completed ZIP membership differs from the approved allowlist; extra={extra}; missing={missing}")

    completed_packet = {rel.removeprefix("source-only/"): archive_files[rel] for rel in packet_files}
    if _sha256(completed_packet["manifest.json"]) != APPROVED_PACKET_MANIFEST_SHA256:
        raise BaselineGateError("embedded original manifest is not the approved packet manifest")
    sidecar_parts = completed_packet["manifest.sha256"].decode("ascii").strip().split()
    if not sidecar_parts or sidecar_parts[0] != manifest_hash:
        raise BaselineGateError("embedded manifest sidecar differs from the approved source-only packet")
    if _sha256(completed_packet[manifest["source_metadata_path"]]) != manifest["source_metadata_sha256"]:
        raise BaselineGateError("embedded source metadata hash differs from the approved packet")

    answer_hash_record = _read_json_bytes(archive_files["MODEL_ASSISTED_ANSWER_HASHES.json"], "MODEL_ASSISTED_ANSWER_HASHES.json")
    expected_answer_names = {Path(rel).name for rel in manifest["answer_files"]}
    if set(answer_hash_record) != expected_answer_names:
        raise BaselineGateError("model-assisted answer hash list does not contain exactly eleven approved answers")
    answer_hashes: dict[str, str] = {}
    for rel in manifest["answer_files"]:
        name = Path(rel).name
        raw = completed_packet[rel]
        if _sha256(raw) != answer_hash_record[name]:
            raise BaselineGateError(f"completed answer hash does not match the supplied answer list: {name}")
        try:
            answer_text = raw.decode("utf-8")
        except UnicodeDecodeError as exc:
            raise BaselineGateError(f"completed answer is not UTF-8: {name}") from exc
        if ("**Answer status:** `COMPLETE`" not in answer_text
                or f"**Packet manifest SHA-256:** `{manifest_hash}`" not in answer_text
                or "[[REQUIRED]]" in answer_text):
            raise BaselineGateError(f"completed answer is incomplete or not bound to the approved manifest: {name}")
        answer_hashes[rel] = answer_hash_record[name]

    # Source representations and frozen task definitions must match the original
    # approved packet byte-for-byte; no archive content is interpreted or repaired.
    for rel in [row["path"] for row in manifest["sources"]] + [row["path"] for row in manifest["task_forms"]]:
        if completed_packet[rel] != (original / rel).read_bytes():
            raise BaselineGateError(f"completed ZIP changed a source representation or fixed task form: {rel}")
    for row in manifest["sources"]:
        if _sha256(completed_packet[row["path"]]) != row["representation_sha256"]:
            raise BaselineGateError(f"completed ZIP source hash differs from the original manifest: {row['path']}")
    for row in manifest["task_forms"]:
        if _sha256(completed_packet[row["path"]]) != row["sha256"]:
            raise BaselineGateError(f"completed ZIP task hash differs from the original manifest: {row['path']}")

    note_raw = archive_files["MODEL_ASSISTED_COMPLETION_NOTE.md"]
    try:
        note = note_raw.decode("utf-8")
    except UnicodeDecodeError as exc:
        raise BaselineGateError("completion note is not UTF-8") from exc
    if (MODEL_ASSISTED_REVIEWER_ROLE not in note or "No product-value candidate output" not in note
            or "No baseline lock was created." not in note):
        raise BaselineGateError("completion note does not establish the approved model-assisted role and no-candidate history")
    projection_path = original.parent / "projection-evaluation" / "PROJECTION_REVIEW_FORM.md"
    if archive_files["projection-evaluation/PROJECTION_REVIEW_FORM.md"] != projection_path.read_bytes():
        raise BaselineGateError("projection evaluation form differs from the approved fixed template")

    source_rows = _read_json_bytes(completed_packet[manifest["source_metadata_path"]], "source-metadata.json")["sources"]
    source_hashes = {row["representation_path"]: row["representation_sha256"] for row in source_rows}
    task_hashes = {row["path"]: row["sha256"] for row in manifest["task_forms"]}
    lock = {
        "status": MODEL_ASSISTED_LOCK_STATUS,
        "experiment_id": EXPERIMENT_ID,
        "source_packet_manifest_sha256": manifest_hash,
        "completed_zip_sha256": APPROVED_MODEL_ASSISTED_ZIP_SHA256,
        "completed_answer_sha256": answer_hashes,
        "source_representation_sha256": source_hashes,
        "task_form_sha256": task_hashes,
        "reviewer": "ChatGPT",
        "reviewer_role": MODEL_ASSISTED_REVIEWER_ROLE,
        "completion_note_sha256": _sha256(note_raw),
        "answer_hash_list_sha256": _sha256(archive_files["MODEL_ASSISTED_ANSWER_HASHES.json"]),
        "product_owner_acceptance": {"accepted": True, "identity": "Greg", "date": accepted_at.date().isoformat()},
        "lock_timestamp": accepted_at.astimezone(timezone.utc).isoformat(),
        "no_new_product_value_candidate_generation_preceded_lock": True,
    }
    lock_raw = (json.dumps(lock, ensure_ascii=False, sort_keys=True, separators=(",", ":")) + "\n").encode("utf-8")
    lock_hash = _sha256(lock_raw)
    destination.parent.mkdir(parents=True, exist_ok=True)
    staging = Path(tempfile.mkdtemp(prefix=".pv-baseline-import-", dir=destination.parent))
    try:
        for rel, raw in archive_files.items():
            output = staging.joinpath(*Path(rel).parts)
            output.parent.mkdir(parents=True, exist_ok=True)
            output.write_bytes(raw)
        lock_path = staging / "source-only" / "source-only-baseline.lock.json"
        with lock_path.open("xb") as stream:
            stream.write(lock_raw)
            stream.flush()
            os.fsync(stream.fileno())
        lock_path.chmod(0o444)
        validate_source_only_packet(staging / "source-only")
        if (staging / "source-only" / "source-only-baseline.lock.json").read_bytes() != lock_raw:
            raise BaselineGateError("model-assisted baseline lock changed during import")
        os.replace(staging, destination)
    except Exception:
        if staging.exists():
            shutil.rmtree(staging)
        raise
    return {
        "destination": str(destination),
        "source_packet_manifest_sha256": manifest_hash,
        "completed_zip_sha256": APPROVED_MODEL_ASSISTED_ZIP_SHA256,
        "lock_sha256": lock_hash,
        "lock_status": MODEL_ASSISTED_LOCK_STATUS,
    }


def _read_json_bytes(raw: bytes, name: str) -> dict:
    try:
        value = json.loads(raw.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise BaselineGateError(f"invalid UTF-8 JSON: {name}") from exc
    if not isinstance(value, dict):
        raise BaselineGateError(f"expected JSON object: {name}")
    return value


def lock_source_only_baseline(
    packet_dir: str | Path, *, completed_at: datetime, analyst_identity: str = "Greg",
) -> str:
    """Create the post-completion lock once; this must not be called for blank forms."""
    root = Path(packet_dir).resolve(strict=True)
    manifest_hash = validate_source_only_packet(root)
    manifest, _ = _manifest(root)
    if completed_at.tzinfo is None or completed_at.utcoffset() is None:
        raise BaselineGateError("completion timestamp must include a timezone")
    if analyst_identity != "Greg" or manifest.get("analyst_role") != "HUMAN_SOURCE_ONLY_ANALYST":
        raise BaselineGateError("only the approved human source-only analyst may lock this packet")
    answers = _answer_hashes(root, manifest)
    lock = {
        "status": "SOURCE_ONLY_BASELINE_LOCKED",
        "packet_id": manifest["packet_id"],
        "source_packet_manifest_sha256": manifest_hash,
        "completed_answer_sha256": answers,
        "completion_timestamp": completed_at.astimezone(timezone.utc).isoformat(),
        "analyst_identity": analyst_identity,
        "analyst_role": "HUMAN_SOURCE_ONLY_ANALYST",
        "statement": LOCK_STATEMENT,
    }
    path = root / "source-only-baseline.lock.json"
    payload = (json.dumps(lock, ensure_ascii=False, sort_keys=True, separators=(",", ":")) + "\n").encode("utf-8")
    try:
        with path.open("xb") as stream:
            stream.write(payload)
            stream.flush()
            os.fsync(stream.fileno())
        path.chmod(0o444)
    except FileExistsError as exc:
        raise BaselineGateError("baseline lock already exists; normal workflow never rewrites it") from exc
    return _sha256(payload)


@dataclass(frozen=True)
class ProviderPolicyAttestation:
    share_inputs_and_outputs_with_openai_disabled: bool
    attested_by: str
    observed_at: datetime


@dataclass(frozen=True)
class ProviderRightsRevalidation:
    representation_sha256: str
    status: str
    revalidated_at: datetime


@dataclass(frozen=True)
class CampaignAttempt:
    subject_abn: str
    capability: str
    request_id: str
    maximum_exposure_aud: Decimal


def validate_campaign_budget(attempts: Sequence[CampaignAttempt]) -> Decimal:
    """Validate the approved per-physical-attempt and aggregate AUD ceilings."""
    total = Decimal("0")
    for attempt in attempts:
        try:
            amount = Decimal(attempt.maximum_exposure_aud)
        except (InvalidOperation, TypeError) as exc:
            raise BaselineGateError("attempt exposure must be a finite AUD amount") from exc
        if not amount.is_finite() or amount < 0 or amount > MAX_ATTEMPT_AUD:
            raise BaselineGateError("per-attempt conservative exposure exceeds AUD 0.25")
        total += amount
    if total > MAX_CAMPAIGN_AUD:
        raise BaselineGateError("aggregate conservative exposure exceeds AUD 2.00")
    return total


def certify_five_request_campaign_shape(attempts: Sequence[CampaignAttempt]) -> Decimal:
    """Certify the fixed initial product-value plan, excluding sparse controls."""
    if len(attempts) != len(PROPOSED_CAPABILITY_BY_ABN):
        raise BaselineGateError("offline campaign must contain exactly the five approved subject requests")
    subjects = [attempt.subject_abn for attempt in attempts]
    request_ids = [attempt.request_id for attempt in attempts]
    if len(set(subjects)) != len(subjects):
        raise BaselineGateError("offline campaign permits one request per approved subject")
    if set(subjects) != set(PROPOSED_CAPABILITY_BY_ABN):
        raise BaselineGateError("offline campaign subjects must match the fixed five-subject cohort")
    if any(attempt.capability != PROPOSED_CAPABILITY_BY_ABN[attempt.subject_abn] for attempt in attempts):
        raise BaselineGateError("offline campaign capability routes must match the fixed Outcomes/Commitments plan")
    if any(not isinstance(request_id, str) or not request_id.strip() for request_id in request_ids):
        raise BaselineGateError("offline campaign requests require immutable request identities")
    if len(set(request_ids)) != len(request_ids):
        raise BaselineGateError("offline campaign request identities must be unique")
    return validate_campaign_budget(attempts)


def require_campaign_ready(
    packet_dir: str | Path,
    *,
    candidate_generation_at: datetime,
    provider_attestation: ProviderPolicyAttestation,
    provider_rights_revalidated: Mapping[str, ProviderRightsRevalidation],
    certified_request_ids: frozenset[str],
    attempts: Sequence[CampaignAttempt],
    now: datetime,
) -> str:
    """Require all human, evidence, rights, policy, identity and budget gates."""
    root = Path(packet_dir).resolve(strict=True)
    manifest_hash = validate_source_only_packet(root)
    manifest, _ = _manifest(root)
    lock_path = root / "source-only-baseline.lock.json"
    if not lock_path.is_file():
        raise BaselineGateError("candidate generation is blocked until the source-only baseline is locked")
    lock = _read_json(lock_path)
    lock_status = lock.get("status")
    if lock.get("source_packet_manifest_sha256") != manifest_hash:
        raise BaselineGateError("baseline lock does not bind the exact current packet manifest")
    if lock_status == MODEL_ASSISTED_LOCK_STATUS:
        acceptance = lock.get("product_owner_acceptance", {})
        note_path = root.parent / "MODEL_ASSISTED_COMPLETION_NOTE.md"
        hash_list_path = root.parent / "MODEL_ASSISTED_ANSWER_HASHES.json"
        current_sources = {
            row["representation_path"]: row["representation_sha256"]
            for row in _read_json(root / manifest["source_metadata_path"])["sources"]
        }
        current_tasks = {row["path"]: row["sha256"] for row in manifest["task_forms"]}
        if (lock.get("completed_zip_sha256") != APPROVED_MODEL_ASSISTED_ZIP_SHA256
                or lock.get("experiment_id") != EXPERIMENT_ID
                or lock.get("reviewer_role") != MODEL_ASSISTED_REVIEWER_ROLE
                or lock.get("reviewer") != "ChatGPT"
                or acceptance != {"accepted": True, "identity": "Greg", "date": "2026-09-14"}
                or lock.get("no_new_product_value_candidate_generation_preceded_lock") is not True
                or lock.get("source_representation_sha256") != current_sources
                or lock.get("task_form_sha256") != current_tasks
                or not note_path.is_file() or _sha256(note_path.read_bytes()) != lock.get("completion_note_sha256")
                or not hash_list_path.is_file() or _sha256(hash_list_path.read_bytes()) != lock.get("answer_hash_list_sha256")):
            raise BaselineGateError("model-assisted baseline lock lacks the exact ZIP, reviewer, acceptance, source/task or note binding")
        if lock.get("statement") is not None:
            raise BaselineGateError("model-assisted source-only baseline must not be represented by the human-lock statement")
        locked_at_value = lock.get("lock_timestamp")
    elif lock_status == "SOURCE_ONLY_BASELINE_LOCKED" and lock.get("statement") == LOCK_STATEMENT:
        locked_at_value = lock.get("completion_timestamp")
    else:
        raise BaselineGateError("baseline lock status is not an explicitly accepted human or model-assisted mode")
    if lock.get("completed_answer_sha256") != _answer_hashes(root, manifest):
        raise BaselineGateError("locked answer files changed after baseline completion")
    locked_at = datetime.fromisoformat(locked_at_value)
    if candidate_generation_at.tzinfo is None or now.tzinfo is None:
        raise BaselineGateError("candidate-generation and current timestamps must include timezones")
    if candidate_generation_at <= locked_at or candidate_generation_at > now:
        raise BaselineGateError("candidate generation must occur after baseline lock and not in the future")
    attested = provider_attestation.observed_at
    if (provider_attestation.share_inputs_and_outputs_with_openai_disabled is not True
            or provider_attestation.attested_by != "Greg"
            or attested.tzinfo is None or now - attested > PROVIDER_ATTESTATION_MAX_AGE
            or attested > now):
        raise BaselineGateError("fresh owner-attested provider sharing setting Disabled is required")
    if not attempts or len(attempts) > MAX_ATTEMPTS:
        raise BaselineGateError("campaign must contain between one and five predeclared physical attempts")
    subjects = [attempt.subject_abn for attempt in attempts]
    if len(subjects) != len(set(subjects)):
        raise BaselineGateError("repeat attempts are not authorized; one physical attempt per subject maximum")
    if not set(subjects) <= EXPECTED_ABNS:
        raise BaselineGateError("campaign includes a subject outside the frozen cohort")
    request_ids = [attempt.request_id for attempt in attempts]
    if (any(not isinstance(value, str) or not value.strip() for value in request_ids)
            or len(request_ids) != len(set(request_ids))):
        raise BaselineGateError("every physical attempt must have a unique certified request identity")
    if (set(request_ids) != set(certified_request_ids)
            or any(attempt.capability != PROPOSED_CAPABILITY_BY_ABN.get(attempt.subject_abn) for attempt in attempts)):
        raise BaselineGateError("request identities or capability routes do not match the fixed offline campaign plan")
    rights_by_hash = {
        row["provider_rights_decision_id"]: row["representation_sha256"]
        for row in _read_json(root / manifest["source_metadata_path"])["sources"]
        if row["abn"] in set(subjects)
    }
    if not rights_by_hash:
        raise BaselineGateError("campaign has no source-specific provider-rights basis")
    for decision_id, representation_hash in rights_by_hash.items():
        revalidation = provider_rights_revalidated.get(decision_id)
        if (revalidation is None or revalidation.representation_sha256 != representation_hash
                or revalidation.status != "authorized" or revalidation.revalidated_at.tzinfo is None
                or revalidation.revalidated_at.utcoffset() is None
                or now - revalidation.revalidated_at > PROVIDER_ATTESTATION_MAX_AGE
                or revalidation.revalidated_at > now):
            raise BaselineGateError("exact provider-transmission rights have not been freshly revalidated for every attempted source hash")
    validate_campaign_budget(attempts)
    return manifest_hash
