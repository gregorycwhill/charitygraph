import base64
import hashlib
import json
import subprocess
from datetime import datetime, timezone
from pathlib import Path

import pytest

from bridge.bridge import CutoverWatcher
from bridge.g4_doc_export_ingress import (
    DOC_EXPORT_PREFIX,
    DOC_EXPORT_SUFFIX,
    DocExportContext,
    DocExportError,
    parse_doc_export,
    read_doc_export,
    scan_doc_exports,
)
from charitygraph.autonomous_loop import (
    ClaimUnavailable,
    DuplicateInstruction,
    InstructionEnvelope,
    LocalAutonomousBridge,
    canonical_json,
)


ALLOWLIST = (
    "bridge/bridge.py",
    "bridge/g4_doc_export_ingress.py",
    "tests/test_bridge_doc_export_ingress.py",
    "reports/G4_DOC_EXPORT_SECOND_INGRESS_DORMANT_IMPLEMENTATION_20261031.md",
)


def _context() -> DocExportContext:
    workspace = Path(__file__).resolve().parents[1]
    head = subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=workspace, text=True).strip()
    branch = subprocess.check_output(["git", "branch", "--show-current"], cwd=workspace, text=True).strip()
    fence = {
        "schema": "charitygraph.g4-o1b-dormant-fence/v1",
        "state": "ACTIVE",
        "workspace_path": str(workspace.resolve()),
        "branch": branch,
        "head": head,
        "legacy_execution": "FENCED",
    }
    fence_bytes = json.dumps(fence, sort_keys=True, separators=(",", ":")).encode("utf-8")
    return DocExportContext(
        repository="charitygraph",
        workspace_path=str(workspace.resolve()),
        branch=branch,
        head=head,
        fence_bytes=fence_bytes,
        allowed_paths=ALLOWLIST,
    )


def _envelope(context: DocExportContext, instruction_id: str = "gate4:doc-export:1") -> InstructionEnvelope:
    return InstructionEnvelope.create(
        instruction_id=instruction_id,
        content="Implement only the bounded local reliability task and write the report.",
        target={
            "repository": context.repository,
            "workspace_path": context.workspace_path,
            "branch": context.branch,
            "head": context.head,
            "model": "luna-high",
        },
        operation="codex_engineering",
        authority={"source": "chatgpt", "approved": True, "authority_envelope": "gate4-engineering"},
        execution={
            "mode": "codex_exec",
            "change_policy": "bounded_workspace",
            "model": "luna-high",
            "report_path": ALLOWLIST[-1],
            "timeout_seconds": 300,
            "authority_version": "charitygraph.g4-o1d-local-implementation/v1",
            "scope": "bounded_local_builder_code_change",
            "allowed_paths": list(ALLOWLIST),
            "commit_policy": "local_commit_only",
        },
        created_at=datetime(2026, 10, 31, tzinfo=timezone.utc),
    )


def _instruction_bytes(envelope: InstructionEnvelope) -> bytes:
    return (canonical_json(envelope.as_dict()) + "\n").encode("utf-8")


def _export(raw_instruction: bytes, *, bom: bool = False, expected_sha: str | None = None) -> bytes:
    encoded = base64.urlsafe_b64encode(raw_instruction).rstrip(b"=")
    digest = expected_sha or hashlib.sha256(raw_instruction).hexdigest()
    wrapper = b"CGDOC1:" + encoded + b":" + digest.encode("ascii")
    return (b"\xef\xbb\xbf" if bom else b"") + wrapper


def test_bom_and_no_bom_no_lf_roundtrip_preserve_exact_instruction_bytes(tmp_path):
    context = _context()
    raw = _instruction_bytes(_envelope(context))
    for index, bom in enumerate((True, False)):
        path = tmp_path / f"{DOC_EXPORT_PREFIX}roundtrip-{index}{DOC_EXPORT_SUFFIX}"
        path.write_bytes(_export(raw, bom=bom))
        decoded = read_doc_export(path, artifacts_root=tmp_path, context=context)
        assert decoded.raw_instruction_bytes == raw
        assert decoded.raw_instruction_sha256 == hashlib.sha256(raw).hexdigest()
        assert decoded.envelope.instruction_id == "gate4:doc-export:1"


def test_wrapper_and_embedded_identity_are_exact(tmp_path):
    context = _context()
    raw = _instruction_bytes(_envelope(context, "gate4:doc-export:identity"))
    decoded = parse_doc_export(
        _export(raw),
        filename=f"{DOC_EXPORT_PREFIX}identity{DOC_EXPORT_SUFFIX}",
        context=context,
    )
    assert decoded.raw_instruction_sha256 == hashlib.sha256(raw).hexdigest()
    assert decoded.envelope.authority == {
        "source": "chatgpt",
        "approved": True,
        "authority_envelope": "gate4-engineering",
    }
    assert decoded.envelope.target["head"] == context.head
    assert decoded.envelope.execution["allowed_paths"] == list(ALLOWLIST)


@pytest.mark.parametrize(
    "mutate",
    [
        lambda raw: raw[:-1],  # missing the required trailing LF in the embedded instruction
        lambda raw: raw.replace(b"\n", b"\r\n"),
        lambda raw: json.dumps(json.loads(raw), indent=2).encode("utf-8") + b"\n",
        lambda raw: raw.replace(b'"operation":"codex_engineering"', b'"operation":"codex_engineering","operation":"codex_engineering"'),
    ],
)
def test_newline_pretty_and_duplicate_tampering_is_rejected(mutate):
    context = _context()
    raw = mutate(_instruction_bytes(_envelope(context, "gate4:doc-export:tamper")))
    with pytest.raises(DocExportError):
        parse_doc_export(_export(raw), filename=f"{DOC_EXPORT_PREFIX}tamper{DOC_EXPORT_SUFFIX}", context=context)


def test_payload_hash_tamper_is_rejected():
    context = _context()
    raw = _instruction_bytes(_envelope(context, "gate4:doc-export:hash"))
    export = _export(raw)
    tampered = export[:-1] + (b"0" if export[-1:] != b"0" else b"1")
    with pytest.raises(DocExportError, match="SHA-256"):
        parse_doc_export(tampered, filename=f"{DOC_EXPORT_PREFIX}hash{DOC_EXPORT_SUFFIX}", context=context)


def test_malformed_wrapper_is_rejected():
    context = _context()
    with pytest.raises(DocExportError):
        parse_doc_export(
            b"CGDOC1:not*base64:00",
            filename=f"{DOC_EXPORT_PREFIX}malformed.txt",
            context=context,
        )


@pytest.mark.parametrize(
    "filename",
    [
        "cg-g4-o1b-doc-export-.txt",
        "cg-g4-o1b-doc-export-../escape.txt",
        "cg-g4-o1b-doc-export-http://example.txt",
        "cg-g4-o1b-instruction-not-doc.txt",
    ],
)
def test_filename_and_path_traversal_are_rejected(tmp_path, filename):
    context = _context()
    raw = _instruction_bytes(_envelope(context, "gate4:doc-export:path"))
    with pytest.raises(DocExportError):
        read_doc_export(tmp_path / filename, artifacts_root=tmp_path, context=context)


def test_wrong_head_or_fence_identity_is_rejected():
    context = _context()
    raw = _instruction_bytes(_envelope(context, "gate4:doc-export:fence"))
    wrong_head = DocExportContext(
        repository=context.repository,
        workspace_path=context.workspace_path,
        branch=context.branch,
        head="0" * 40,
        fence_bytes=context.fence_bytes,
        allowed_paths=context.allowed_paths,
    )
    with pytest.raises(DocExportError):
        parse_doc_export(_export(raw), filename=f"{DOC_EXPORT_PREFIX}head.txt", context=wrong_head)
    tampered_fence = context.fence_bytes.replace(b"ACTIVE", b"BROKEN")
    wrong_fence = DocExportContext(
        repository=context.repository,
        workspace_path=context.workspace_path,
        branch=context.branch,
        head=context.head,
        fence_bytes=tampered_fence,
        allowed_paths=context.allowed_paths,
    )
    with pytest.raises(DocExportError):
        parse_doc_export(_export(raw), filename=f"{DOC_EXPORT_PREFIX}fence.txt", context=wrong_fence)


def test_authority_operation_schema_and_allowlist_are_fail_closed():
    context = _context()
    envelope = _envelope(context, "gate4:doc-export:policy")
    cases = []
    for field, value in (("schema_version", "wrong/v1"), ("operation", "bridge_probe")):
        raw = envelope.as_dict()
        raw[field] = value
        cases.append((canonical_json(raw) + "\n").encode("utf-8"))
    raw = envelope.as_dict()
    raw["authority"] = {"source": "chatgpt", "approved": False, "authority_envelope": "gate4-engineering"}
    cases.append((canonical_json(raw) + "\n").encode("utf-8"))
    raw = envelope.as_dict()
    raw["execution"]["allowed_paths"] = ["../escape.txt"]
    cases.append((canonical_json(raw) + "\n").encode("utf-8"))
    for candidate in cases:
        with pytest.raises(DocExportError):
            parse_doc_export(_export(candidate), filename=f"{DOC_EXPORT_PREFIX}policy.txt", context=context)


def test_doc_export_scanner_is_dormant_and_live_raw_json_regression_remains(tmp_path):
    context = _context()
    export = tmp_path / f"{DOC_EXPORT_PREFIX}dormant.txt"
    export.write_bytes(_export(_instruction_bytes(_envelope(context, "gate4:doc-export:dormant"))))
    raw_json = tmp_path / "cg-g4-o1b-instruction-raw.json"
    raw_json_bytes = _instruction_bytes(_envelope(context, "gate4:doc-export:raw"))
    raw_json.write_bytes(raw_json_bytes)
    assert scan_doc_exports(tmp_path) == ()
    assert scan_doc_exports(tmp_path, activate=True) == ()

    watcher = CutoverWatcher(
        artifacts_root=tmp_path,
        workspace_root=Path(__file__).resolve().parents[1],
        runtime_root=tmp_path / "runtime",
    )
    assert watcher._candidate_paths() == [raw_json]
    assert raw_json.read_bytes() == raw_json_bytes


def test_existing_ledger_keeps_single_claim_and_rejects_conflicting_identity(tmp_path):
    context = _context()
    envelope = _envelope(context, "gate4:doc-export:ledger")
    bridge = LocalAutonomousBridge(tmp_path / "bridge", workspace=context.workspace_path).open()
    first = bridge.submit(envelope)
    assert first["accepted"] is True
    duplicate = bridge.submit(envelope)
    assert duplicate["duplicate"] is True
    conflicting = InstructionEnvelope.create(
        instruction_id=envelope.instruction_id,
        content="a different immutable instruction",
        target=envelope.target,
        operation=envelope.operation,
        authority=envelope.authority,
        execution=envelope.execution,
        created_at=datetime(2026, 10, 31, tzinfo=timezone.utc),
    )
    with pytest.raises(DuplicateInstruction):
        bridge.submit(conflicting)
    claimed = bridge.claim(owner="doc-export-test")
    assert claimed.instruction_id == envelope.instruction_id
    with pytest.raises(ClaimUnavailable):
        bridge.claim(owner="second-owner")
