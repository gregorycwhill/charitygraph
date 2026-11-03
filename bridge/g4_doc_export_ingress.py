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
import os
import re
import stat
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from charitygraph.autonomous_loop import InstructionEnvelope, InvalidInstruction, canonical_json


DOC_EXPORT_PREFIX = "cg-g4-o1b-doc-export-"
DOC_EXPORT_SUFFIX = ".txt"
DOC_EXPORT_MAGIC = "CGDOC1"
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
class DocExportScanConfig:
    """Explicit host capability for the otherwise dormant scanner."""

    enabled: bool = False
    trusted_root: str = ""


@dataclass(frozen=True)
class DocExport:
    """Validated export and the exact instruction bytes it contains."""

    path: Path | None
    raw_instruction_bytes: bytes
    raw_instruction_sha256: str
    export_sha256: str
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
        export_sha256=hashlib.sha256(raw).hexdigest(),
        envelope=envelope,
    )


def _has_reparse_attribute(value: os.stat_result) -> bool:
    return bool(getattr(value, "st_file_attributes", 0) & getattr(stat, "FILE_ATTRIBUTE_REPARSE_POINT", 0x400))


def _reject_non_regular(path: Path, value: os.stat_result, *, label: str) -> None:
    if path.is_symlink() or _has_reparse_attribute(value) or not stat.S_ISREG(value.st_mode):
        raise DocExportError(f"{label} must be a non-link regular file")


def _same_file_identity(left: os.stat_result, right: os.stat_result) -> bool:
    return (left.st_dev, left.st_ino, left.st_mode) == (right.st_dev, right.st_ino, right.st_mode)


def _open_no_follow(path: Path) -> int:
    """Open a regular file without following a final link/reparse point."""
    if os.name != "nt":
        flags = os.O_RDONLY | getattr(os, "O_NOFOLLOW", 0)
        return os.open(path, flags)

    # Windows has no portable O_NOFOLLOW.  OPEN_REPARSE_POINT makes a final
    # reparse point open as the link itself, so the subsequent regular-file
    # check fails closed instead of following a junction/symlink target.
    import ctypes
    import msvcrt

    kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
    kernel32.CreateFileW.argtypes = [
        ctypes.c_wchar_p,
        ctypes.c_uint32,
        ctypes.c_uint32,
        ctypes.c_void_p,
        ctypes.c_uint32,
        ctypes.c_uint32,
        ctypes.c_void_p,
    ]
    kernel32.CreateFileW.restype = ctypes.c_void_p
    handle = kernel32.CreateFileW(
        str(path),
        0x80000000,  # GENERIC_READ
        0x00000001 | 0x00000002 | 0x00000004,  # share read/write/delete
        None,
        3,  # OPEN_EXISTING
        0x00200000,  # FILE_FLAG_OPEN_REPARSE_POINT
        None,
    )
    invalid = ctypes.c_void_p(-1).value
    if handle in {None, invalid}:
        error = ctypes.get_last_error()
        raise OSError(error, f"CreateFileW failed for {path}")
    try:
        return msvcrt.open_osfhandle(handle, os.O_RDONLY | getattr(os, "O_BINARY", 0))
    except BaseException:
        kernel32.CloseHandle(handle)
        raise


def _read_regular_file_no_follow(path: Path) -> bytes:
    """Read one stable regular-file identity through an opened descriptor."""
    try:
        before = path.lstat()
        _reject_non_regular(path, before, label="Doc export")
        fd = _open_no_follow(path)
        with os.fdopen(fd, "rb", closefd=True) as stream:
            opened = os.fstat(stream.fileno())
            if not _same_file_identity(before, opened):
                raise DocExportError("Doc export file identity changed before read")
            raw = stream.read()
            after = os.fstat(stream.fileno())
            if not _same_file_identity(opened, after):
                raise DocExportError("Doc export file identity changed during read")
            return raw
    except DocExportError:
        raise
    except OSError as exc:
        raise DocExportError("Doc export could not be read without following a link") from exc


def _direct_child(path: str | Path, root: Path) -> Path:
    source = Path(path)
    if source.is_absolute():
        if source.parent != root:
            raise DocExportError("Doc export must be a direct child of the trusted artifacts folder")
        return source
    if len(source.parts) != 1:
        raise DocExportError("Doc export path must be one direct-child filename")
    return root / source.name


def read_doc_export(path: str | Path, *, artifacts_root: str | Path, context: DocExportContext) -> DocExport:
    """Read one safe direct-child export from the trusted artifacts folder."""
    root_input = Path(artifacts_root)
    try:
        root_input_stat = root_input.lstat()
    except OSError as exc:
        raise DocExportError("trusted artifacts folder is not a regular directory") from exc
    if root_input.is_symlink() or _has_reparse_attribute(root_input_stat):
        raise DocExportError("trusted artifacts folder is not a regular directory")
    root = root_input.resolve()
    if not root.is_dir() or _has_reparse_attribute(root.lstat()):
        raise DocExportError("trusted artifacts folder is not a regular directory")
    source = _direct_child(path, root)
    _safe_filename(source.name)
    raw = _read_regular_file_no_follow(source)
    value = parse_doc_export(raw, filename=source.name, context=context)
    return DocExport(
        path=source,
        raw_instruction_bytes=value.raw_instruction_bytes,
        raw_instruction_sha256=value.raw_instruction_sha256,
        export_sha256=value.export_sha256,
        envelope=value.envelope,
    )


def scan_doc_exports(artifacts_root: str | Path, *, config: DocExportScanConfig | None = None) -> tuple[Path, ...]:
    """List safe exports only with an explicit trusted host capability.

    The default is intentionally empty.  A mutable module flag is not an
    activation mechanism; the caller must provide a fresh explicit config
    bound to the exact trusted root.
    """
    if config is None or not config.enabled:
        return ()
    root_input = Path(artifacts_root)
    try:
        root_input_stat = root_input.lstat()
    except OSError:
        return ()
    if root_input.is_symlink() or _has_reparse_attribute(root_input_stat):
        return ()
    root = root_input.resolve()
    if config.trusted_root != str(root) or not root.is_dir():
        return ()
    if _has_reparse_attribute(root.lstat()):
        return ()
    candidates: list[Path] = []
    for path in root.iterdir():
        if not path.name.startswith(DOC_EXPORT_PREFIX) or not path.name.endswith(DOC_EXPORT_SUFFIX):
            continue
        if not _SAFE_NAME.fullmatch(path.name[len(DOC_EXPORT_PREFIX) : -len(DOC_EXPORT_SUFFIX)]):
            continue
        try:
            value = path.lstat()
            _reject_non_regular(path, value, label="Doc export")
        except (DocExportError, OSError):
            continue
        candidates.append(path)
    return tuple(sorted(candidates))


__all__ = [
    "DOC_EXPORT_MAGIC",
    "DOC_EXPORT_PREFIX",
    "DOC_EXPORT_SUFFIX",
    "DocExport",
    "DocExportContext",
    "DocExportError",
    "DocExportScanConfig",
    "parse_doc_export",
    "read_doc_export",
    "scan_doc_exports",
]
