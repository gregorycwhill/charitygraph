import hashlib
import json
from datetime import datetime, timedelta, timezone
from dataclasses import replace
from decimal import Decimal
from pathlib import Path

import pytest

import charitygraph.product_value_baseline as baseline
from charitygraph.product_value_baseline import (
    BaselineGateError,
    CampaignAttempt,
    ProviderPolicyAttestation,
    ProviderRightsRevalidation,
    lock_source_only_baseline,
    require_campaign_ready,
    validate_campaign_budget,
    validate_source_only_packet,
)


ABNS = ["28004778081", "78053639115", "50169561394", "61002643852",
        "65159324697", "32565549842", "80009663478", "57057493017"]
NAMES = ["World Vision Australia", "Bush Heritage Australia", "Australian Red Cross Society",
         "Greenpeace Australia Pacific", "The Sunrise Project Australia", "St George Community Housing Limited",
         "Royal Flying Doctor Service of Australia (Queensland Section)", "The Leukaemia Foundation of Australia Limited"]
NOW = datetime(2026, 9, 14, 3, 0, tzinfo=timezone.utc)


def digest(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def write_json(path: Path, value: dict) -> bytes:
    raw = (json.dumps(value, sort_keys=True, separators=(",", ":")) + "\n").encode()
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(raw)
    return raw


def make_packet(root: Path) -> Path:
    root.mkdir(parents=True)
    sources = []
    source_metadata = []
    for subject_index, abn in enumerate(ABNS):
        for kind in ("acnc", "report"):
            rel = f"representations/{abn}/{kind}.txt"
            raw = f"approved source representation {abn} {kind}\n".encode()
            (root / rel).parent.mkdir(parents=True, exist_ok=True)
            (root / rel).write_bytes(raw)
            artifact = f"srcblob:{abn}-{kind}"
            sources.append({"abn": abn, "path": rel, "representation_sha256": digest(raw), "source_artifact_id": artifact})
            source_metadata.append({
                "abn": abn, "representation_path": rel, "representation_sha256": digest(raw),
                "source_artifact_id": artifact, "subject_id": f"subject:{abn}", "subject_name": f"Subject {abn}",
                "subject_name_source": f"Subject {abn}", "source_record_id": f"srcrec:{abn}-{kind}",
                "source_role": "financial_report" if kind == "report" else "historical_frozen_regulator_material",
                "legal_scope": "organisation", "evidence_locator_id": f"locator:{abn}-{kind}",
                "retention_status": "authorized", "retention_policy_id": "CG_BOUNDED_LOCAL_ANALYTICAL_RETENTION_V1",
                "retention_policy_version": "1.0.0", "retention_decision_id": f"retentiondecision:{abn}-{kind}",
                "retention_review_due": "2027-09-14", "public_redistribution_status": "not_authorized",
                "provider_rights_decision_id": f"rightsdecision:{abn}-{kind}",
                "provider_transmission_status": "separately_authorized_for_exact_hash_subject_to_revalidation",
            })
    metadata = {"metadata_version": "1.0", "sources": source_metadata}
    metadata_raw = write_json(root / "source-metadata.json", metadata)
    forms = []
    answer_files = []
    names = [f"inspect-{abn}.md" for abn in ABNS] + [
        "compare-a-greenpeace-sunrise.md", "compare-b-world-vision-bush-heritage.md",
        "compare-c-st-george-rfds.md",
    ]
    for name in names:
        form_rel = f"forms/{name}"
        raw = f"# Fixed source-only task {name}\n".encode()
        (root / form_rel).parent.mkdir(exist_ok=True)
        (root / form_rel).write_bytes(raw)
        forms.append({"path": form_rel, "sha256": digest(raw)})
        answer_rel = f"answers/{name}"
        answer_files.append(answer_rel)
        (root / answer_rel).parent.mkdir(exist_ok=True)
        (root / answer_rel).write_text(
            "**Answer status:** `NOT_STARTED`\n**Packet manifest SHA-256:** `[[REQUIRED]]`\n", encoding="utf-8"
        )
    (root / "README.md").write_text("Private fixed source-only baseline packet.\n", encoding="utf-8")
    manifest = {
        "packet_id": "product-value-source-only-baseline-2026-09-14", "packet_version": "1.0",
        "status": "AWAITING_HUMAN_SOURCE_ONLY_COMPLETION", "analyst_identity": "Greg",
        "analyst_role": "HUMAN_SOURCE_ONLY_ANALYST", "created_at_utc": "2026-09-14T00:00:00+00:00",
        "cohort": [{"abn": abn, "name": name, "subject_id": f"subject:{abn}"}
                   for abn, name in zip(ABNS, NAMES, strict=True)],
        "sources": sources, "source_metadata_path": "source-metadata.json",
        "source_metadata_sha256": digest(metadata_raw), "task_forms": forms,
        "comparison_question_sha256": {Path(row["path"]).name: row["sha256"] for row in forms if "compare-" in row["path"]},
        "answer_files": answer_files, "lock_record_path": "source-only-baseline.lock.json",
        "required_lock_statement": "SOURCE_ONLY_BASELINE_LOCKED_BEFORE_NEW_CANDIDATE_GENERATION",
        "source_only_tree_policy": "No candidate, projection or adjudication artifacts.",
    }
    raw = write_json(root / "manifest.json", manifest)
    (root / "manifest.sha256").write_text(digest(raw) + "  manifest.json\n", encoding="ascii")
    baseline.APPROVED_PACKET_MANIFEST_SHA256 = digest(raw)
    return root


def complete_answers(root: Path) -> None:
    manifest = json.loads((root / "manifest.json").read_text(encoding="utf-8"))
    manifest_hash = digest((root / "manifest.json").read_bytes())
    for rel in manifest["answer_files"]:
        (root / rel).write_text(
            f"**Answer status:** `COMPLETE`\n**Packet manifest SHA-256:** `{manifest_hash}`\nAnswer: reviewed.\n",
            encoding="utf-8",
        )


def attestation(at=NOW, disabled=True):
    return ProviderPolicyAttestation(disabled, "Greg", at)


def attempts(count=5):
    capabilities = ["outcomes", "outcomes", "commitments", "commitments", "commitments"]
    return [CampaignAttempt(ABNS[i], capabilities[i], f"request:pv-{i}", Decimal("0.25")) for i in range(count)]


def rights(packet: Path, selected_attempts, *, at=NOW, status="authorized"):
    rows = json.loads((packet / "source-metadata.json").read_text(encoding="utf-8"))["sources"]
    subjects = {attempt.subject_abn for attempt in selected_attempts}
    return {row["provider_rights_decision_id"]: ProviderRightsRevalidation(
                row["representation_sha256"], status, at)
            for row in rows if row["abn"] in subjects}


def test_packet_manifest_source_identity_and_exact_representation_hashes(tmp_path):
    packet = make_packet(tmp_path / "packet")
    manifest_hash = digest((packet / "manifest.json").read_bytes())
    assert validate_source_only_packet(packet) == manifest_hash
    previous = baseline.APPROVED_PACKET_MANIFEST_SHA256
    baseline.APPROVED_PACKET_MANIFEST_SHA256 = "0" * 64
    with pytest.raises(BaselineGateError, match="approved frozen source-only baseline"):
        validate_source_only_packet(packet)
    baseline.APPROVED_PACKET_MANIFEST_SHA256 = previous
    source = packet / "representations" / ABNS[0] / "acnc.txt"
    source.write_text("changed source", encoding="utf-8")
    with pytest.raises(BaselineGateError, match="representation hash mismatch"):
        validate_source_only_packet(packet)


def test_incomplete_forms_cannot_lock_and_candidate_generation_is_blocked_before_lock(tmp_path):
    packet = make_packet(tmp_path / "packet")
    with pytest.raises(BaselineGateError, match="incomplete"):
        lock_source_only_baseline(packet, completed_at=NOW)
    with pytest.raises(BaselineGateError, match="until the source-only baseline is locked"):
        require_campaign_ready(packet, candidate_generation_at=NOW, provider_attestation=attestation(),
                               provider_rights_revalidated=rights(packet, attempts()),
                               certified_request_ids=frozenset(a.request_id for a in attempts()), attempts=attempts(), now=NOW)


def test_lock_binds_completed_answer_hashes_and_answer_mutation_invalidates_it(tmp_path):
    packet = make_packet(tmp_path / "packet")
    complete_answers(packet)
    lock_source_only_baseline(packet, completed_at=NOW)
    lock_record = json.loads((packet / "source-only-baseline.lock.json").read_text(encoding="utf-8"))
    assert lock_record["status"] == "SOURCE_ONLY_BASELINE_LOCKED"
    with pytest.raises(BaselineGateError, match="already exists"):
        lock_source_only_baseline(packet, completed_at=NOW + timedelta(seconds=1))
    lock = packet / "source-only-baseline.lock.json"
    lock.chmod(0o666)
    answer = packet / "answers" / f"inspect-{ABNS[0]}.md"
    answer.write_text(answer.read_text(encoding="utf-8") + "changed after lock\n", encoding="utf-8")
    with pytest.raises(BaselineGateError, match="changed after baseline completion"):
        require_campaign_ready(packet, candidate_generation_at=NOW + timedelta(seconds=2),
                               provider_attestation=attestation(), provider_rights_revalidated=rights(packet, attempts()),
                               certified_request_ids=frozenset(a.request_id for a in attempts()),
                               attempts=attempts(), now=NOW + timedelta(seconds=3))


def test_candidate_projection_or_adjudication_artifacts_fail_closed(tmp_path):
    packet = make_packet(tmp_path / "packet")
    (packet / "candidate-output.json").write_text("{}", encoding="utf-8")
    with pytest.raises(BaselineGateError, match="unapproved artifacts"):
        validate_source_only_packet(packet)


def test_rights_axes_are_independent_and_public_redistribution_stays_prohibited(tmp_path):
    packet = make_packet(tmp_path / "packet")
    metadata_path = packet / "source-metadata.json"
    metadata = json.loads(metadata_path.read_text(encoding="utf-8"))
    metadata["sources"][0]["public_redistribution_status"] = "authorized"
    metadata_raw = write_json(metadata_path, metadata)
    manifest_path = packet / "manifest.json"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    manifest["source_metadata_sha256"] = digest(metadata_raw)
    manifest_raw = write_json(manifest_path, manifest)
    (packet / "manifest.sha256").write_text(digest(manifest_raw) + "  manifest.json\n", encoding="ascii")
    baseline.APPROVED_PACKET_MANIFEST_SHA256 = digest(manifest_raw)
    with pytest.raises(BaselineGateError, match="public redistribution"):
        validate_source_only_packet(packet)


def test_provider_policy_rights_revalidation_freshness_and_budget_gates(tmp_path):
    packet = make_packet(tmp_path / "packet")
    complete_answers(packet)
    lock_source_only_baseline(packet, completed_at=NOW)
    base = dict(packet_dir=packet, candidate_generation_at=NOW + timedelta(seconds=1),
                provider_attestation=attestation(), provider_rights_revalidated=rights(packet, attempts()),
                certified_request_ids=frozenset(a.request_id for a in attempts()),
                attempts=attempts(), now=NOW + timedelta(seconds=2))
    assert require_campaign_ready(**base)
    with pytest.raises(BaselineGateError, match="Disabled"):
        require_campaign_ready(**{**base, "provider_attestation": attestation(disabled=False)})
    with pytest.raises(BaselineGateError, match="Disabled"):
        require_campaign_ready(**{**base, "provider_attestation": attestation(at=NOW - timedelta(minutes=16))})
    with pytest.raises(BaselineGateError, match="rights"):
        require_campaign_ready(**{**base, "provider_rights_revalidated": {}})
    wrong_hash = rights(packet, attempts())
    first_key = next(iter(wrong_hash))
    wrong_hash[first_key] = replace(wrong_hash[first_key], representation_sha256="0" * 64)
    with pytest.raises(BaselineGateError, match="exact provider-transmission rights"):
        require_campaign_ready(**{**base, "provider_rights_revalidated": wrong_hash})
    stale_rights = rights(packet, attempts(), at=NOW - timedelta(minutes=16))
    with pytest.raises(BaselineGateError, match="exact provider-transmission rights"):
        require_campaign_ready(**{**base, "provider_rights_revalidated": stale_rights})
    unauthorized_rights = rights(packet, attempts(), status="not_authorized")
    with pytest.raises(BaselineGateError, match="exact provider-transmission rights"):
        require_campaign_ready(**{**base, "provider_rights_revalidated": unauthorized_rights})
    over_attempt = [CampaignAttempt(ABNS[0], "outcomes", "request:pv-0", Decimal("0.26"))]
    with pytest.raises(BaselineGateError, match="per-attempt"):
        require_campaign_ready(**{**base, "attempts": over_attempt,
                                  "provider_rights_revalidated": rights(packet, over_attempt),
                                  "certified_request_ids": frozenset({"request:pv-0"})})
    duplicate = [CampaignAttempt(ABNS[0], "outcomes", "request:a", Decimal("0.10")),
                 CampaignAttempt(ABNS[0], "outcomes", "request:b", Decimal("0.10"))]
    with pytest.raises(BaselineGateError, match="repeat attempts"):
        require_campaign_ready(**{**base, "attempts": duplicate})
    uncertified = [CampaignAttempt(ABNS[0], "outcomes", "request:unknown", Decimal("0.01"))]
    with pytest.raises(BaselineGateError, match="identities or capability"):
        require_campaign_ready(**{**base, "attempts": uncertified})


def test_aggregate_campaign_budget_cap_is_enforced_independently():
    over_aggregate = [CampaignAttempt(ABNS[i % 5], "outcomes" if i % 5 < 2 else "commitments",
                                     f"request:budget-{i}", Decimal("0.25")) for i in range(9)]
    with pytest.raises(BaselineGateError, match="aggregate conservative exposure"):
        validate_campaign_budget(over_aggregate)


def test_candidate_generation_must_postdate_lock_and_request_ids_are_unique(tmp_path):
    packet = make_packet(tmp_path / "packet")
    complete_answers(packet)
    lock_source_only_baseline(packet, completed_at=NOW)
    args = dict(packet_dir=packet, provider_attestation=attestation(), provider_rights_revalidated=rights(packet, attempts()),
                certified_request_ids=frozenset(a.request_id for a in attempts()),
                attempts=attempts(), now=NOW + timedelta(seconds=1))
    with pytest.raises(BaselineGateError, match="after baseline lock"):
        require_campaign_ready(**args, candidate_generation_at=NOW)
    duplicate_ids = [CampaignAttempt(ABNS[i], "outcomes", "request:same", Decimal("0.10")) for i in range(2)]
    with pytest.raises(BaselineGateError, match="unique certified"):
        require_campaign_ready(**{**args, "attempts": duplicate_ids}, candidate_generation_at=NOW + timedelta(milliseconds=1))
    wrong_route = [CampaignAttempt(ABNS[0], "commitments", "request:pv-0", Decimal("0.10"))]
    with pytest.raises(BaselineGateError, match="identities or capability"):
        require_campaign_ready(**{**args, "attempts": wrong_route}, candidate_generation_at=NOW + timedelta(milliseconds=1))
