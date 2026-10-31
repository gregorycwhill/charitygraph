"""Pure, dormant decoder for connected Google Docs text/plain instruction exports.

This module is deliberately not a watcher or a transport.  It accepts only a
direct child of a caller-supplied trusted artifacts directory and returns the
exact embedded raw instruction bytes after fail-closed validation.  Live bridge
pickup remains disabled until a separately authorised integration supplies a
verified fence/context and explicitly calls the decoder.
"""
from __future__ import annotations

import base64
import hashlib
import json
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from charitygraph.autonomous_loop import InstructionEnvelope, InvalidInstruction, canonical_json


DOC_EXPORT_PREFIX = "cg-g4-o1b-doc-export-"
DOC_EXPORT_SUFFIX = ".txt"
DOC_EXPORT_MAGIC = "CGDOC1"
DOC_EXPORT_INGRESS_ACTIVE = False
INSTRUCTION_SCHEMA = "charitygraph.autonomous-instruction/v1"
ENGINEERING_OPERATION = "codex_engineering"
ENGINEERING_MODEL = "luna-high"
ENGINEERING_AUTHORITY = {
    "source": "chatgpt",
    "approved": True,
    "authority_envelope": "gate4-engineering",
}
FENCE_SCHEMA = "charitygraph.g4-o1b-dormant-fence/v1"

_SAFE_NAME = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_.-]*$")
_HEX_SHA256 = re.compile(r"^[0-9a-f]{64}$")
_HEAD = re.compile(r"^[0-9a-f]{40}$")
_BASE64URL = re.compile(r"^[A-Za-z0-9_-]+$")


class DocExportError(InvalidInstruction):
    """A malformed or unauthorised dormant Doc export."""


@dataclass(frozen=True)
class DocExportContext:
    """Verified local identity required before a Doc export may be admitted."""

    repository: str
    workspace_path: str
    branch: str
    head: str
    fence_bytes: bytes
    allowed_paths: tuple[str, ...]


@dataclass(frozen=True)
class DocExport:
    """Validated export and the exact instruction bytes it contains."""

    path: Path | None
    raw_instruction_bytes: bytes
    raw_instruction_sha256: str
    envelope: InstructionEnvelope


def _reject_duplicate_keys(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    value: dict[str, Any] = {}
    for key, item in pairs:
        if key in value:
            raise DocExportError(f"duplicate JSON key: {key}")
        value[key] = item
    return value


def _reject_non_json_constant(value: str) -> None:
    raise DocExportError(f"non-standard JSON constant is not permitted: {value}")


def _safe_filename(filename: str) -> None:
    if not filename.startswith(DOC_EXPORT_PREFIX) or not filename.endswith(DOC_EXPORT_SUFFIX):
        raise DocExportError("Doc export filename is outside the inert allowlist")
    stem = filename[len(DOC_EXPORT_PREFIX) : -len(DOC_EXPORT_SUFFIX)]
    if not stem or stem in {".", ".."} or not _SAFE_NAME.fullmatch(stem):
        raise DocExportError("Doc export filename contains an unsafe identity")


def _safe_relative_path(value: Any, *, field: str) -> str:
    if not isinstance(value, str) or not value:
        raise DocExportError(f"{field} must be a non-empty relative path")
    normalised = value.replace("\\", "/")
    if normalised.startswith("/") or ":" in normalised:
        raise DocExportError(f"{field} must remain relative")
    parts = normalised.split("/")
    if any(part in {"", ".", ".."} for part in parts):
        raise DocExportError(f"{field} must not contain traversal components")
    return normalised


def _validate_fence(context: DocExportContext) -> str:
    if context.repository != "charitygraph":
        raise DocExportError("context repository is not charitygraph")
    if not context.workspace_path or not context.branch:
        raise DocExportError("verified workspace and branch are required")
    if not _HEAD.fullmatch(context.head):
        raise DocExportError("verified HEAD must be a full lowercase commit identity")
    fence_sha256 = hashlib.sha256(context.fence_bytes).hexdigest()
    try:
        fence = json.loads(
            context.fence_bytes.decode("utf-8"),
            object_pairs_hook=_reject_duplicate_keys,
            parse_constant=_reject_non_json_constant,
        )
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise DocExportError("verified fence bytes are not valid JSON") from exc
    if not isinstance(fence, dict):
        raise DocExportError("verified fence must be a JSON object")
    if (
        fence.get("schema") != FENCE_SCHEMA
        or fence.get("state") != "ACTIVE"
        or fence.get("workspace_path") != context.workspace_path
        or fence.get("branch") != context.branch
        or fence.get("head") != context.head
    ):
        raise DocExportError("verified fence identity does not match the target context")
    return fence_sha256


def _validate_engineering_envelope(envelope: InstructionEnvelope, context: DocExportContext) -> None:
    # InstructionEnvelope.from_dict above is the existing repository validator;
    # these checks are the narrower Doc-export admission policy layered on it.
    if envelope.schema_version != INSTRUCTION_SCHEMA:
        raise DocExportError("Doc export instruction schema_version is unsupported")
    if envelope.operation != ENGINEERING_OPERATION:
        raise DocExportError("Doc export operation is not codex_engineering")
    if envelope.authority != ENGINEERING_AUTHORITY:
        raise DocExportError("Doc export authority envelope is not exact")

    target = envelope.target
    if (
        target.get("repository") != context.repository
        or target.get("workspace_path") != context.workspace_path
        or target.get("branch") != context.branch
        or target.get("head") != context.head
        or target.get("model") != ENGINEERING_MODEL
    ):
        raise DocExportError("Doc export target does not match the verified workspace/fence")

    execution = envelope.execution
    if not isinstance(execution, dict):
        raise DocExportError("Doc export engineering instruction requires execution")
    required = {
        "mode",
        "change_policy",
        "model",
        "report_path",
        "timeout_seconds",
        "authority_version",
        "scope",
        "allowed_paths",
        "commit_policy",
    }
    if set(execution) != required:
        raise DocExportError("Doc export execution fields are not the bounded engineering contract")
    if (
        execution["mode"] != "codex_exec"
        or execution["change_policy"] != "bounded_workspace"
        or execution["model"] != ENGINEERING_MODEL
        or execution["authority_version"] != "charitygraph.g4-o1d-local-implementation/v1"
        or execution["scope"] != "bounded_local_builder_code_change"
        or execution["commit_policy"] != "local_commit_only"
    ):
        raise DocExportError("Doc export execution authority is unsupported")
    timeout = execution["timeout_seconds"]
    if isinstance(timeout, bool) or not isinstance(timeout, int) or not 30 <= timeout <= 900:
        raise DocExportError("Doc export timeout_seconds must be an integer from 30 to 900")

    report_path = _safe_relative_path(execution["report_path"], field="execution.report_path")
    if not report_path.startswith("reports/") or not report_path.endswith((".md", ".json", ".txt")):
        raise DocExportError("Doc export report_path must be a readable reports/ path")
    allowed = execution["allowed_paths"]
    if not isinstance(allowed, list) or not allowed or not all(isinstance(item, str) for item in allowed):
        raise DocExportError("Doc export allowed_paths must be a non-empty list")
    normalised_allowed = tuple(_safe_relative_path(item, field="execution.allowed_paths") for item in allowed)
    expected_allowed = tuple(_safe_relative_path(item, field="context.allowed_paths") for item in context.allowed_paths)
    if len(set(normalised_allowed)) != len(normalised_allowed) or tuple(sorted(normalised_allowed)) != tuple(sorted(expected_allowed)):
        raise DocExportError("Doc export allowed_paths do not match the verified allowlist")
    if report_path not in normalised_allowed:
        raise DocExportError("Doc export report_path must be included in allowed_paths")
    if len(envelope.content.encode("utf-8")) > 12000:
        raise DocExportError("Doc export content exceeds the bounded prompt limit")


def _decode_wrapper(raw: bytes) -> bytes:
    if raw.startswith(b"\xef\xbb\xbf"):
        raw = raw[3:]
    if not raw or b"\n" in raw or b"\r" in raw:
        raise DocExportError("Doc export must be one ASCII wrapper line without a final newline")
    try:
        wrapper = raw.decode("ascii")
    except UnicodeDecodeError as exc:
        raise DocExportError("Doc export wrapper must be ASCII") from exc
    parts = wrapper.split(":")
    if len(parts) != 3 or parts[0] != DOC_EXPORT_MAGIC:
        raise DocExportError("Doc export wrapper magic or field count is invalid")
    encoded, expected_sha256 = parts[1:]
    if not _BASE64URL.fullmatch(encoded) or "=" in encoded:
        raise DocExportError("Doc export payload is not unpadded base64url")
    if not _HEX_SHA256.fullmatch(expected_sha256):
        raise DocExportError("Doc export payload SHA-256 is not lowercase hexadecimal")
    if len(encoded) % 4 == 1:
        raise DocExportError("Doc export payload has invalid base64url length")
    try:
        embedded = base64.urlsafe_b64decode(encoded + "=" * (-len(encoded) % 4))
    except (ValueError, base64.binascii.Error) as exc:
        raise DocExportError("Doc export payload is not valid base64url") from exc
    if not embedded or hashlib.sha256(embedded).hexdigest() != expected_sha256:
        raise DocExportError("Doc export payload SHA-256 does not match exact embedded bytes")
    return embedded


def parse_doc_export(raw: bytes, *, filename: str, context: DocExportContext) -> DocExport:
    """Validate a text/plain export and return its exact embedded instruction."""
    _safe_filename(filename)
    _validate_fence(context)
    embedded = _decode_wrapper(raw)
    if embedded.startswith(b"\xef\xbb\xbf"):
        raise DocExportError("embedded instruction must not contain a UTF-8 BOM")
    try:
        text = embedded.decode("utf-8")
    except UnicodeDecodeError as exc:
        raise DocExportError("embedded instruction must be UTF-8") from exc
    if not text.endswith("\n") or text.count("\n") != 1 or "\r" in text:
        raise DocExportError("embedded instruction must have exactly one trailing LF")
    try:
        raw_object = json.loads(
            text,
            object_pairs_hook=_reject_duplicate_keys,
            parse_constant=_reject_non_json_constant,
        )
    except (json.JSONDecodeError, DocExportError) as exc:
        if isinstance(exc, DocExportError):
            raise
        raise DocExportError("embedded instruction is not strict JSON") from exc
    if not isinstance(raw_object, dict):
        raise DocExportError("embedded instruction must be a JSON object")
    if (canonical_json(raw_object) + "\n").encode("utf-8") != embedded:
        raise DocExportError("embedded instruction is not sorted compact canonical JSON")
    try:
        envelope = InstructionEnvelope.from_dict(raw_object)
    except InvalidInstruction as exc:
        raise DocExportError(str(exc)) from exc
    _validate_engineering_envelope(envelope, context)
    return DocExport(
        path=None,
        raw_instruction_bytes=embedded,
        raw_instruction_sha256=hashlib.sha256(embedded).hexdigest(),
        envelope=envelope,
    )


def read_doc_export(path: str | Path, *, artifacts_root: str | Path, context: DocExportContext) -> DocExport:
    """Read one safe direct-child export from the trusted artifacts folder."""
    source = Path(path)
    root = Path(artifacts_root).resolve()
    if any(part in {".", ".."} for part in source.parts):
        raise DocExportError("Doc export path contains traversal components")
    resolved = source.resolve()
    if resolved.parent != root:
        raise DocExportError("Doc export must be a direct child of the trusted artifacts folder")
    _safe_filename(source.name)
    try:
        raw = resolved.read_bytes()
    except OSError as exc:
        raise DocExportError("Doc export could not be read") from exc
    value = parse_doc_export(raw, filename=source.name, context=context)
    return DocExport(path=resolved, raw_instruction_bytes=value.raw_instruction_bytes, raw_instruction_sha256=value.raw_instruction_sha256, envelope=value.envelope)


def scan_doc_exports(artifacts_root: str | Path, *, activate: bool = False) -> tuple[Path, ...]:
    """List safe exports only when a future caller explicitly activates it.

    The live bridge never calls this function.  Its default is intentionally
    empty, making the second logical ingress dormant by construction.
    """
    if not activate or not DOC_EXPORT_INGRESS_ACTIVE:
        return ()
    root = Path(artifacts_root).resolve()
    if not root.is_dir():
        return ()
    return tuple(
        sorted(
            path
            for path in root.iterdir()
            if path.is_file()
            and path.name.startswith(DOC_EXPORT_PREFIX)
            and path.name.endswith(DOC_EXPORT_SUFFIX)
            and _SAFE_NAME.fullmatch(path.name[len(DOC_EXPORT_PREFIX) : -len(DOC_EXPORT_SUFFIX)])
        )
    )


__all__ = [
    "DOC_EXPORT_INGRESS_ACTIVE",
    "DOC_EXPORT_MAGIC",
    "DOC_EXPORT_PREFIX",
    "DOC_EXPORT_SUFFIX",
    "DocExport",
    "DocExportContext",
    "DocExportError",
    "parse_doc_export",
    "read_doc_export",
    "scan_doc_exports",
]
