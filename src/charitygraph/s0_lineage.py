"""Read-only, hash-pinned S0 package selection and immutable identity checks."""
from __future__ import annotations

import hashlib
import json
from pathlib import Path

from .scale_s0 import ScalePreflightError

LINEAGE_FILE = "SCALE_S0_IDENTITY_LINEAGE_V1.json"


def artifact_hash(path: Path) -> str:
    text = path.read_text(encoding="utf-8")
    try:
        text = json.dumps(json.loads(text), sort_keys=True, separators=(",", ":"), ensure_ascii=False)
    except json.JSONDecodeError:
        # The binding registry is YAML. Universal-newline decoding makes this
        # repository-text digest independent of Git's Windows checkout mode.
        pass
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def validate_lineage(root: Path) -> dict:
    try:
        lineage = json.loads((root / LINEAGE_FILE).read_text(encoding="utf-8"))
        if lineage["schema"] != "urn:charitygraph:s0:identity-lineage" or lineage["version"] != 1:
            raise ValueError("unsupported lineage")
        definitions = {}
        entries = {entry["path"]: entry for entry in lineage["artifacts"]}
        paths = set()
        for entry in lineage["artifacts"]:
            relative = entry["path"]
            path = (root / relative).resolve()
            if not path.is_relative_to(root.resolve()) or relative in paths:
                raise ValueError("duplicate or escaping artifact path")
            paths.add(relative)
            if "supersedes_path" in entry:
                predecessor = entries[entry["supersedes_path"]]
                if (entry["identity"] == predecessor["identity"]
                        or int(entry["version"]) != int(predecessor["version"]) + 1):
                    raise ValueError("successor requires distinct identity and next version")
            digest = artifact_hash(path)
            if digest != entry["sha256"]:
                raise ValueError(f"immutable artifact hash drift: {relative}")
            if entry["role"] == "historical_evidence_only":
                if relative != "SCALE_S0_SHADOW_MANDATE_V2.yaml" or digest != "9e5f41dcc74d95f1d939927c1710949f416495e850a37098aa76f99c2811a386":
                    raise ValueError("unrecognised historical identity exception")
                continue
            body = json.loads(path.read_text(encoding="utf-8")) if entry["kind"] != "registry" else {}
            kind = entry["kind"]
            if kind != "registry":
                identity = body[f"{kind}_id"]
                version = str(body[f"{kind}_version"])
                if (identity, version) != (entry["identity"], entry["version"]):
                    raise ValueError("artifact identity/version drift")
            else:
                identity = entry["identity"]
            key = (kind, identity)
            if key in definitions and definitions[key] != digest:
                raise ValueError("duplicate stable identity with different immutable bytes")
            definitions[key] = digest
        candidates = set(p.relative_to(root).as_posix() for p in (root / "policies/scale-s0").glob("*.yaml"))
        for pattern in ("SCALE_S0_POLICY_BUNDLE_*.yaml", "SCALE_S0_SHADOW_MANDATE_V*.yaml", "SCALE_S0_MANDATE_AUTHORISED_V*.yaml"):
            candidates.update(p.relative_to(root).as_posix() for p in root.glob(pattern))
        if not candidates.issubset(paths):
            raise ValueError("unregistered S0 immutable artifact")
        for package in lineage["packages"].values():
            if not {package["bundle"], package["production"], package["shadow"]}.issubset(paths):
                raise ValueError("unregistered package artifact")
        return lineage
    except (OSError, ValueError, KeyError, TypeError) as error:
        raise ScalePreflightError(f"S0 immutable lineage validation failed: {error}") from error


def resolve_package(root: Path, *, historical: bool = False) -> dict:
    if (root / LINEAGE_FILE).exists():
        lineage = validate_lineage(root)
        return lineage["packages"]["historical_attempt8_17" if historical else "current"]
    if historical or any(root.glob("SCALE_S0_*_V3.yaml")):
        raise ScalePreflightError("S0 successor or historical selection requires immutable lineage registry")
    # Compatibility with original, independently pinned historical checkouts.
    return {"bundle": "SCALE_S0_POLICY_BUNDLE_BALANCED_V1.yaml",
            "production": "SCALE_S0_MANDATE_AUTHORISED_V2.yaml",
            "shadow": "SCALE_S0_SHADOW_MANDATE_V2.yaml"}
